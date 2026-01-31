import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login

# WebAuthn imports
from webauthn import (
    generate_registration_options,
    verify_registration_response,
    options_to_json,
    base64url_to_bytes,
)
from webauthn.helpers import bytes_to_base64url
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
)

from .models import User, PasskeyCredential
from .utils import RP_ID, RP_NAME, ORIGIN


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
