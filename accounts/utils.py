from webauthn.helpers import bytes_to_base64url
from django.conf import settings

# In Produktion muss das deine echte Domain sein!
RP_ID = "localhost"
RP_NAME = "Omas Bilderrahmen"
ORIGIN = "http://localhost:8000"

def get_rp_id():
    return RP_ID

def get_origin():
    return ORIGIN
