from django.urls import path
from django.views.generic import TemplateView
from . import views

urlpatterns = [
    path('register/', TemplateView.as_view(template_name='register.html'), name='register_page'),
    path('register/options/', views.register_options, name='register_options'),
    path('register/verify/', views.register_verify, name='register_verify'),
]