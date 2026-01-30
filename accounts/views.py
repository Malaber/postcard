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
from webauthn.helpers.structs import (
    AuthenticatorSelectionCriteria,
    UserVerificationRequirement,
    RegistrationCredentialSource,
)

from .models import User, PasskeyCredential
from .utils import RP_ID, RP_NAME, ORIGIN


def register_options(request):
    """Schritt 1: Der Browser fragt nach einer Challenge"""

    # Der Username kommt vom Frontend
    username = request.GET.get('username')
    if not username:
        return HttpResponseBadRequest("Username fehlt")

    # Prüfen ob User schon existiert
    if User.objects.filter(username=username).exists():
        return HttpResponseBadRequest("User existiert schon")

    # Optionen generieren (Challenge erstellen)
    options = generate_registration_options(
        rp_id=RP_ID,
        rp_name=RP_NAME,
        user_id=username.encode(),  # Als Bytes für WebAuthn
        user_name=username,
        user_display_name=username,
        authenticator_selection=AuthenticatorSelectionCriteria(
            user_verification=UserVerificationRequirement.PREFERRED
        ),
    )

    # WICHTIG: Challenge in der Session speichern, damit wir sie später prüfen können!
    request.session['challenge'] = options.challenge.decode('utf-8')  # als String speichern

    # JSON an Frontend schicken
    return JsonResponse(json.loads(options_to_json(options)))


@csrf_exempt  # Für den Prototyp einfacher, später mit CSRF Token
def register_verify(request):
    """Schritt 2: Der Browser schickt die signierte Antwort"""

    try:
        data = json.loads(request.body)
        username = data.get('username')

        # Challenge aus Session holen
        expected_challenge = request.session.get('challenge')
        if not expected_challenge:
            return HttpResponseBadRequest("Keine Challenge in Session gefunden")

        # Verifikation durch WebAuthn Library
        verification = verify_registration_response(
            credential=data,
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_origin=ORIGIN,
            expected_rp_id=RP_ID,
        )

        # --- Alles gut! Jetzt User anlegen ---

        # 1. User erstellen
        user = User.objects.create(username=username)

        # 2. Passkey speichern
        PasskeyCredential.objects.create(
            user=user,
            credential_id=verification.credential_id.decode('utf-8'),  # Bytes zu String
            public_key=verification.credential_public_key.decode('utf-8'),  # Bytes zu String
            sign_count=verification.sign_count,
            transports=data.get('response', {}).get('transports', []),
            name="Mein Passkey"
        )

        # 3. User direkt einloggen
        login(request, user)

        # Session aufräumen
        del request.session['challenge']

        return JsonResponse({"status": "ok", "user": username})

    except Exception as e:
        print(f"Fehler: {e}")
        return HttpResponseBadRequest(f"Verifikation fehlgeschlagen: {e}")
