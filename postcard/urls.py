from django.urls import path
from . import views

urlpatterns = [
    # We use the internal UUID (frame_id) here because this is for the OWNER
    path('frame/<uuid:frame_id>/upload/', views.upload_view, name='frame_upload'),
]
