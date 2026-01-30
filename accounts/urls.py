from django.urls import path
from . import views

urlpatterns = [
    path('register/options/', views.register_options, name='register_options'),
    path('register/verify/', views.register_verify, name='register_verify'),
]
