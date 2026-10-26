"""Fixed native callback, S256 PKCE, one-use codes, revocable hashed tokens."""
import base64
import hashlib
import re
import secrets
from datetime import timedelta
from functools import wraps
from urllib.parse import urlencode

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from .models import AuthFlow, MobileSession
from .views import json_endpoint


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def issue_token(user):
    token = secrets.token_urlsafe(32)
    MobileSession.objects.create(token_hash=digest(token), user=user,
                                 expires_at=timezone.now() + timedelta(days=30))
    return token


def bearer_required(fn):
    @wraps(fn)
    def wrapped(request, *args, **kwargs):
        header = request.headers.get('Authorization', '')
        session = MobileSession.objects.select_related('user').filter(
            token_hash=digest(header[7:]), expires_at__gt=timezone.now(), user__is_active=True
        ).first() if header.startswith('Bearer ') else None
        if not session:
            return JsonResponse({'detail': 'Please sign in again.'}, status=401)
        request.user = session.user
        request.mobile_session = session
        response = fn(request, *args, **kwargs)
        response['Cache-Control'] = 'no-store'
        return response
    # These endpoints NEVER accept cookie authentication.
    return csrf_exempt(wrapped)


@require_GET
def authorize(request):
    state, challenge = request.GET.get('state', ''), request.GET.get('code_challenge', '')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43,128}', state) or not re.fullmatch(r'[A-Za-z0-9_-]{43}', challenge):
        return JsonResponse({'detail': 'Invalid PKCE request'}, status=400)
    if not request.user.is_authenticated:
        return redirect('/auth/login/?' + urlencode({'next': request.get_full_path()}))
    code = secrets.token_urlsafe(32)
    AuthFlow.objects.create(id=digest(code), kind='mobile',
        payload={'challenge': challenge, 'user_id': str(request.user.id)},
        expires_at=timezone.now() + timedelta(minutes=2))
    response = HttpResponse(status=302)
    response['Location'] = 'de.malaber.postcard://auth?' + urlencode({'code': code, 'state': state})
    response['Cache-Control'] = 'no-store'
    response['Referrer-Policy'] = 'no-referrer'
    return response


@csrf_exempt
@require_POST
@json_endpoint
def exchange(request, data):
    verifier = data.get('code_verifier', '')
    if not isinstance(verifier, str) or not re.fullmatch(r'[A-Za-z0-9._~-]{43,128}', verifier):
        raise ValueError('Invalid verifier')
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    from .models import User
    with transaction.atomic():
        query = AuthFlow.objects.filter(id=digest(data.get('code', '')), kind='mobile',
            consumed=False, expires_at__gt=timezone.now(), payload__challenge=challenge)
        flow = query.first()
        if not flow or query.update(consumed=True) != 1:
            return JsonResponse({'detail': 'Sign-in expired. Please try again.'}, status=401)
        user = User.objects.get(id=flow.payload['user_id'], is_active=True)
        token = issue_token(user)
    response = JsonResponse({'access_token': token, 'user_id': str(user.id)})
    response['Cache-Control'] = 'no-store'
    return response


@require_POST
@bearer_required
def logout(request):
    request.mobile_session.delete()
    return HttpResponse(status=204)
