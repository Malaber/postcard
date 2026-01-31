from django.urls import path
from . import views

urlpatterns = [
    path('frame/<uuid:frame_id>/upload/', views.upload_view, name='frame_upload'),
    path('frame/<uuid:frame_id>/', views.frame_detail, name='frame_detail'),
    path('frame/<str:token>/player/', views.frame_kiosk, name='frame_kiosk'),
    path('frame/<str:token>/api/', views.frame_photos_json, name='frame_photos_json'),
    path('photo/<uuid:pk>/delete/', views.PhotoDeleteView.as_view(), name='photo_delete'),
]
