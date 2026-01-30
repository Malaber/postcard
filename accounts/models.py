import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Custom user model. 
    Using UUID for id is safer for public-facing apps than integers.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # We can add profile fields here later (e.g., display_name)

    def __str__(self):
        return self.username


class PasskeyCredential(models.Model):
    """
    Stores WebAuthn credentials (public keys) for passwordless login.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='credentials')

    # The Credential ID (Base64URL encoded string)
    # Max length in spec is 1023 bytes, so 1364 chars in Base64.
    credential_id = models.CharField(max_length=2000, unique=True)

    # The Public Key (Base64URL encoded string or CBOR bytes)
    public_key = models.TextField()

    # Sign Count (prevent replay attacks)
    sign_count = models.PositiveIntegerField(default=0)

    # Hardware/Transport hints (e.g., 'internal' for TouchID, 'usb' for YubiKey)
    transports = models.JSONField(default=list, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField(auto_now=True)

    # User-friendly name for the key (e.g. "MacBook Pro", "iPhone")
    name = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return f"{self.name or 'Passkey'} ({self.user.username})"
