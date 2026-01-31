from webauthn.helpers import bytes_to_base64url
from django.conf import settings

# CRITICAL: This must match your browser URL exactly (without port)
RP_ID = "localhost"

RP_NAME = "Postcard"

# This must match the full URL including scheme and port
ORIGIN = "http://localhost:8000"

def get_rp_id():
    return RP_ID

def get_origin():
    return ORIGIN