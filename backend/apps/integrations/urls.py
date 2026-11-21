from django.urls import path

from . import api

urlpatterns = [
    path("integrations/google/status", api.GoogleStatusView.as_view()),
    path("integrations/google/start", api.google_start),
    path("integrations/google/callback", api.google_callback),
    path("integrations/google/picker-config", api.PickerConfigView.as_view()),
    path("integrations/google/disconnect", api.GoogleDisconnectView.as_view()),
]
