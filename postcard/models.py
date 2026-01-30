from django.db import models
import uuid

def get_file_path(instance, filename):
    ext = filename.split('.')[-1]
    # Wir benennen Dateien in UUIDs um, damit es keine Duplikate gibt
    filename = f"{uuid.uuid4()}.{ext}"
    return f'photos/{filename}'

class Photo(models.Model):
    image = models.ImageField(upload_to=get_file_path)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True) # Soft-Delete Funktion

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Foto vom {self.created_at.strftime('%d.%m.%Y')}"