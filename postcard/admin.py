from django.contrib import admin
from .models import Frame, Photo

@admin.register(Frame)
class FrameAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'access_token', 'created_at')
    readonly_fields = ('access_token',) # Protect token from accidental manual edits

@admin.register(Photo)
class PhotoAdmin(admin.ModelAdmin):
    list_display = ('frame', 'caption', 'uploaded_at')
