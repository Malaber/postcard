from django.urls import path
from . import views

urlpatterns = [
    path('frame/<uuid:frame_id>/upload/', views.upload_view, name='frame_upload'),
    path('frame/<uuid:frame_id>/', views.frame_detail, name='frame_detail'),
]
