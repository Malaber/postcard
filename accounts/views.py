"""Django adapter for the shared Malaber FastPasskey core and browser client."""
import hashlib
import json
import secrets
import uuid
from datetime import timedelta
from functools import wraps
from importlib.resources import files
from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.conf import settings
from django.contrib.auth import login
from django.db import IntegrityError, transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST
from fastpasskey import FastPasskey, PasskeyUser
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url

from .models import AuthFlow, PasskeyCredential, User


def service():
    return FastPasskey(rp_name='Postcard', rp_id=settings.WEBAUTHN_RP_ID, origin=settings.APP_BASE_URL)


def json_endpoint(fn):
    @wraps(fn)
    def wrapped(request, *args, **kwargs):
        try:
            data = json.loads(request.body or '{}')
            if not isinstance(data, dict):
                raise ValueError('Expected a JSON object.')
            return fn(request, data, *args, **kwargs)
        except (ValueError, KeyError, TypeError, ValidationError, IntegrityError, User.DoesNotExist,
                PasskeyCredential.DoesNotExist) as exc:
            return JsonResponse({'detail': 'Request invalid or sign-in expired. Please try again.'}, status=400)
    return wrapped


def begin(request, kind, payload):
    if not request.session.session_key:
        request.session.create()
    AuthFlow.objects.filter(expires_at__lte=timezone.now()).delete()
    flow = AuthFlow.objects.create(id=secrets.token_hex(32), kind=kind, payload=payload,
                                  session_key=request.session.session_key,
                                  expires_at=timezone.now() + timedelta(minutes=5))
    request.session['passkey_flow'] = flow.id


def consume(request, kind):
    query = AuthFlow.objects.filter(id=request.session.get('passkey_flow'), kind=kind,
                                   session_key=request.session.session_key, consumed=False,
                                   expires_at__gt=timezone.now())
    flow = query.first()
    if not flow or query.update(consumed=True) != 1:
        raise ValueError('Expired ceremony')
    return flow.payload


def login_page(request):
    next_url = request.GET.get('next', '/')
    if not url_has_allowed_host_and_scheme(next_url, allowed_hosts=set()) or not next_url.startswith('/'):
        next_url = '/'
    return render(request, 'login.html', {'next_url': next_url})


def asset(request):
    return HttpResponse(files('fastpasskey').joinpath('static/fastpasskey.js').read_text(),
                        content_type='text/javascript')


@require_POST
@json_endpoint
def register_options(request, data):
    adding = request.user.is_authenticated
    username = request.user.username if adding else str(data.get('username', '')).strip()
    if not username or len(username) > 150 or (not adding and User.objects.filter(username=username).exists()):
        raise ValueError('Choose an unused username')
    user_id = request.user.id if adding else uuid.uuid4()
    ceremony = service().begin_registration(
        user=PasskeyUser(id=user_id.bytes, name=username, display_name=username),
        request_host=None, request_base_url=settings.APP_BASE_URL,
        exclude_credential_ids=list(request.user.credentials.values_list('credential_id', flat=True)) if adding else [],
        state_payload={'user_id': str(user_id), 'username': username, 'adding': adding})
    begin(request, 'register', ceremony.state)
    return JsonResponse(ceremony.options)


@require_POST
@json_endpoint
def register_verify(request, data):
    state = consume(request, 'register')
    try:
        result = service().verify_registration(credential=data['credential'], state=state)
    except Exception as exc:
        raise ValueError('Invalid passkey') from exc
    with transaction.atomic():
        if state['adding']:
            if not request.user.is_authenticated or str(request.user.id) != state['user_id']:
                raise ValueError('Account changed')
            user = User.objects.get(id=state['user_id'], is_active=True)
        else:
            user = User(id=state['user_id'], username=state['username'])
            user.set_unusable_password()
            user.save()
        PasskeyCredential.objects.create(user=user, credential_id=bytes_to_base64url(result.credential_id),
            public_key=bytes_to_base64url(result.credential_public_key), sign_count=result.sign_count,
            transports=data['credential'].get('response', {}).get('transports', []), name='Passkey')
    login(request, user)
    return JsonResponse({'user': user.username})


@require_POST
@json_endpoint
def login_options(request, data):
    # Username is optional; it also supports pre-migration non-discoverable keys.
    username = data.get('username')
    ids = list(PasskeyCredential.objects.filter(user__username=username, user__is_active=True)
               .values_list('credential_id', flat=True)) if username else None
    ceremony = service().begin_authentication(request_host=None, request_base_url=settings.APP_BASE_URL,
        allow_credential_ids=ids, state_payload={'username': username})
    begin(request, 'login', ceremony.state)
    return JsonResponse(ceremony.options)


@require_POST
@json_endpoint
def login_verify(request, data):
    state = consume(request, 'login')
    with transaction.atomic():
        key = PasskeyCredential.objects.select_for_update().select_related('user').get(
            credential_id=data['credential']['id'], user__is_active=True)
        if state.get('username') and key.user.username != state['username']:
            raise ValueError('Wrong account')
        try:
            result = service().verify_authentication(credential=data['credential'], state=state,
                credential_public_key=base64url_to_bytes(key.public_key), credential_current_sign_count=key.sign_count)
        except Exception as exc:
            raise ValueError('Invalid passkey') from exc
        key.sign_count = result.new_sign_count
        key.save()
    login(request, key.user)
    return JsonResponse({'user': key.user.username})


from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from fastpasskey import validate_passkey_name


@login_required
def passkeys_page(request):
    return render(request, 'passkeys.html', {'keys': request.user.credentials.all(), 'next_url': '/auth/passkeys/'})


@login_required
@require_POST
@json_endpoint
def rename_passkey(request, data, key_id):
    key = get_object_or_404(PasskeyCredential, id=key_id, user=request.user)
    key.name = validate_passkey_name(data.get('name', ''))
    key.save(update_fields=['name'])
    return JsonResponse({'name': key.name})


@login_required
@require_POST
@json_endpoint
def delete_options(request, data, key_id):
    key = get_object_or_404(PasskeyCredential, id=key_id, user=request.user)
    others = list(request.user.credentials.exclude(id=key.id).values_list('credential_id', flat=True))
    if not others:
        raise ValueError('Keep at least one passkey')
    ceremony = service().begin_authentication(request_host=None, request_base_url=settings.APP_BASE_URL,
        allow_credential_ids=others, state_payload={'key_id': str(key.id), 'user_id': str(request.user.id)})
    begin(request, 'delete', ceremony.state)
    return JsonResponse(ceremony.options)


@login_required
@require_POST
@json_endpoint
def delete_verify(request, data, key_id):
    state = consume(request, 'delete')
    if state['key_id'] != str(key_id) or state['user_id'] != str(request.user.id):
        raise ValueError('Wrong key')
    with transaction.atomic():
        # Lock the owner as well as the credentials to serialize removals.
        User.objects.select_for_update().get(id=request.user.id)
        key = PasskeyCredential.objects.select_for_update().get(
            credential_id=data['credential']['id'], user=request.user)
        if key.id == key_id:
            raise ValueError('Confirm with a different passkey')
        try:
            result = service().verify_authentication(credential=data['credential'], state=state,
                credential_public_key=base64url_to_bytes(key.public_key), credential_current_sign_count=key.sign_count)
        except Exception as exc:
            raise ValueError('Invalid passkey') from exc
        key.sign_count = result.new_sign_count
        key.save()
        request.user.credentials.filter(id=key_id).delete()
    return JsonResponse({'ok': True})
