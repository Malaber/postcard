from django.urls import path
from django.contrib.auth.views import LogoutView
from . import views

urlpatterns = [
    path('passkeys/', views.passkeys_page, name='passkeys'),
    path('passkeys/<uuid:key_id>/rename/', views.rename_passkey),
    path('passkeys/<uuid:key_id>/delete/options/', views.delete_options),
    path('passkeys/<uuid:key_id>/delete/verify/', views.delete_verify),
    path('register/', views.login_page, name='register_page'),
    path('login/', views.login_page, name='login_page'),
    path('register/options/', views.register_options),
    path('register/verify/', views.register_verify),
    path('login/options/', views.login_options),
    path('login/verify/', views.login_verify),
    path('assets/fastpasskey.js', views.asset),
    path('logout/', LogoutView.as_view(next_page='/'), name='logout'),
]
