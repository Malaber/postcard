import uuid
import secrets
from django.db import models
from django.conf import settings


def generate_frame_token():
    """Generates a secure, URL-safe string for the frame's secret link."""
    return secrets.token_urlsafe(32)  # Results in ~43 random characters


def get_file_path(instance, filename):
    ext = filename.split('.')[-1]

    # Ensure the instance has an ID (it usually does due to the default,
    # but this is a safety net for edge cases)
    if not instance.id:
        instance.id = uuid.uuid4()

    # Use the Primary Key as the filename
    new_filename = f"{instance.id}.{ext}"
    return f'photos/{new_filename}'

class Frame(models.Model):
    """
    Represents a physical picture frame.
    Access is controlled via a secret 'access_token' in the URL.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='frames')
    name = models.CharField(max_length=100, help_text="e.g. 'Kitchen Frame' or 'Grandma's House'")

    # The Secret Key. The Frame uses this to fetch photos without a login.
    access_token = models.CharField(
        max_length=64,
        default=generate_frame_token,
        unique=True,
        editable=True  # Allowed to be changed if the URL leaks (Token Rotation)
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.owner.username})"

    def get_viewer_url(self):
        # Update this to match the /p/ prefix we defined in config/urls.py
        return f"/p/frame/{self.access_token}/player/" # TODO use django.url here

class Photo(models.Model):
    """
    A photo uploaded to a specific frame.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    frame = models.ForeignKey(Frame, on_delete=models.CASCADE, related_name='photos')
    is_active = models.BooleanField(default=True) # Soft-Delete

    # The actual image file
    image = models.ImageField(upload_to=get_file_path)

    # Optional message from the uploader
    caption = models.CharField(max_length=255, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # Orientation/Aspect ratio metadata could go here later

    class Meta:
        ordering = ['-created_at']  # Newest first

    def __str__(self):
        return f"Photo for {self.frame.name} ({self.created_at.date()})"

    @property
    def viewer_image_url(self):
        from django.urls import reverse
        return reverse('viewer_photo', args=[self.frame.access_token, self.id])


# Remove uploaded files after successful database deletion, including cascades.
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.db import transaction

@receiver(post_delete, sender=Photo)
def delete_photo_file(sender, instance, **kwargs):
    if instance.image:
        storage, name = instance.image.storage, instance.image.name
        transaction.on_commit(lambda: storage.delete(name))
