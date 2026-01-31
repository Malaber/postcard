from django.urls import path
from django.views.generic import TemplateView
from django.contrib.auth.views import LogoutView  # Import this!
from . import views

urlpatterns = [
    # Registration
    path('register/', TemplateView.as_view(template_name='register.html'), name='register_page'),
    path('register/options/', views.register_options, name='register_options'),
    path('register/verify/', views.register_verify, name='register_verify'),

    # Login (NEW)
    path('login/', TemplateView.as_view(template_name='login.html'), name='login_page'),
    path('login/options/', views.login_options, name='login_options'),
    path('login/verify/', views.login_verify, name='login_verify'),

    # Logout (Django built-in)
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
]
