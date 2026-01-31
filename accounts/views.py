import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login

from webauthn import (
    generate_registration_options,
    verify_registration_response,
    generate_authentication_options,
    verify_authentication_response,

    options_to_json,
    base64url_to_bytes,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    PublicKeyCredentialDescriptor,
    PublicKeyCredentialType,
)


from .models import User, PasskeyCredential
from .utils import RP_ID, RP_NAME, ORIGIN

import traceback


def register_options(request):
    """
    Step 1: The frontend asks for a challenge to sign.
    """
    username = request.GET.get('username')
    if not username:
        return HttpResponseBadRequest("Username missing")

    if User.objects.filter(username=username).exists():
        return HttpResponseBadRequest("User already exists")

    # Generate the options (Challenge)
    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=username.encode(),  # WebAuthn requires bytes for ID
        user_name=username,
        user_display_name=username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED
        ),
    )

    # CRITICAL FIX: Encode bytes to String before storing in Session JSON
    # 'options.challenge' is bytes, session needs string.
    request.session['challenge'] = bytes_to_base64url(options.challenge)

    # Return JSON to frontend
    return JsonResponse(json.loads(options_to_json(options)))


@csrf_exempt
def register_verify(request):
    try:
        data = json.loads(request.body)
        username = data.get('username')

        challenge_b64 = request.session.get('challenge')
        if not challenge_b64:
            # Change this to JSON
            return JsonResponse({"status": "error", "message": "No challenge found in session"}, status=400)

        verification = verify_registration_response(
            credential=data,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
        )

        # ... user creation logic (keep as is) ...
        user = User.objects.create(username=username)

        PasskeyCredential.objects.create(
            user=user,
            credential_id=bytes_to_base64url(verification.credential_id),
            public_key=bytes_to_base64url(verification.credential_public_key),
            sign_count=verification.sign_count,
            transports=data.get('response', {}).get('transports', []),
            name="Primary Passkey"
        )

        login(request, user)
        del request.session['challenge']

        return JsonResponse({"status": "ok", "user": username})

    except Exception as e:
        # 1. Print error to server console
        print(f"!!! VERIFICATION ERROR: {e}")
        # 2. Return JSON so frontend can display it
        return JsonResponse({"status": "error", "message": str(e)}, status=400)


def login_options(request):
    username = request.GET.get('username')
    if not username:
        return HttpResponseBadRequest("Username missing")

    try:
        user = User.objects.get(username=username)
    except User.DoesNotExist:
        return HttpResponseBadRequest("User not found")

    passkeys = PasskeyCredential.objects.filter(user=user)
    if not passkeys.exists():
        return HttpResponseBadRequest("No passkeys found for this user")

    # --- FIX START ---
    # We must use the class 'PublicKeyCredentialDescriptor', not a dictionary!
    allow_credentials = [
        PublicKeyCredentialDescriptor(
            id=base64url_to_bytes(pk.credential_id),
            type=PublicKeyCredentialType.PUBLIC_KEY
        )
        for pk in passkeys
    ]
    # --- FIX END ---

    options = generate_authentication_options(
        rp_id=RP_ID,
        allow_credentials=allow_credentials,  # Pass the list of objects here
    )

    request.session['challenge'] = bytes_to_base64url(options.challenge)

    return JsonResponse(json.loads(options_to_json(options)))


@csrf_exempt
def login_verify(request):
    print("--- DEBUG: Login Verify Started ---")
    try:
        data = json.loads(request.body)
        print(f"DEBUG: Received Data Payload keys: {data.keys()}")
        print(f"DEBUG: Credential ID: {data.get('id')}")

        username = data.get('username')
        user = User.objects.get(username=username)

        credential_id = data.get('id')
        passkey_record = PasskeyCredential.objects.get(credential_id=credential_id, user=user)

        print(f"DEBUG: Found Passkey Record: {passkey_record}")
        print(f"DEBUG: Stored Public Key (First 20 chars): {passkey_record.public_key[:20]}...")
        print(f"DEBUG: Sign Count Type: {type(passkey_record.sign_count)} Value: {passkey_record.sign_count}")

        challenge_b64 = request.session.get('challenge')

        # Die eigentliche Verifikation
        verify_authentication_response(
            credential=data,
            expected_challenge=base64url_to_bytes(challenge_b64),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
            credential_public_key=base64url_to_bytes(passkey_record.public_key),
            credential_current_sign_count=int(passkey_record.sign_count)  # Sicherstellen, dass es int ist
        )

        # Update Sign Count
        new_sign_count = data.get('response', {}).get('authenticatorData', {}).get('signCount')
        if new_sign_count:
            passkey_record.sign_count = new_sign_count
            passkey_record.save()

        login(request, user)
        del request.session['challenge']

        return JsonResponse({"status": "ok", "user": username})

    except Exception as e:
        # Hier drucken wir den Vollen Fehler aus!
        print("!!! LOGIN ERROR TRACEBACK !!!")
        traceback.print_exc()
        print("-----------------------------")
        return JsonResponse({"status": "error", "message": str(e)}, status=400)
