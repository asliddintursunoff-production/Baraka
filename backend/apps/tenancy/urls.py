from django.urls import path

from . import api

urlpatterns = [
    path("auth/login", api.LoginView.as_view()),
    path("auth/logout", api.LogoutView.as_view()),
    path("me", api.MeView.as_view()),
    path("me/business", api.SwitchBusinessView.as_view()),
]
