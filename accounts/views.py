import json
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth import login
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
    username = request.GET.get('username')
    if not username:
        return HttpResponseBadRequest("Username fehlt")

    if User.objects.filter(username=username).exists():
        return HttpResponseBadRequest("User existiert schon")

    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=username.encode(),
        user_name=username,
        user_display_name=username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED
        ),
    )

    # --- KORREKTUR START ---
    # Statt options.challenge.decode('utf-8') nutzen wir bytes_to_base64url()
    request.session['challenge'] = bytes_to_base64url(options.challenge)
    # --- KORREKTUR ENDE ---

    return JsonResponse(json.loads(options_to_json(options)))


@csrf_exempt
def register_verify(request):
    try:
        data = json.loads(request.body)
        username = data.get('username')

        expected_challenge = request.session.get('challenge')
        if not expected_challenge:
            return HttpResponseBadRequest("Keine Challenge in Session gefunden")

        verification = verify_registration_response(
            credential=data,
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
        )

        # User erstellen
        user = User.objects.create(username=username)

        PasskeyCredential.objects.create(
            user=user,
            credential_id=verification.credential_id,
            # Achtung: Hier keine decode() nötig, Library liefert oft schon passendes Format oder wir lassen es so
            public_key=verification.credential_public_key,  # Dito
            sign_count=verification.sign_count,
            transports=data.get('response', {}).get('transports', []),
            name="Mein Passkey"
        )

        login(request, user)
        del request.session['challenge']

        return JsonResponse({"status": "ok", "user": username})

    except Exception as e:
        print(f"VERIFY ERROR: {e}")
        return HttpResponseBadRequest(f"Verifikation fehlgeschlagen: {e}")