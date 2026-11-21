from django.urls import path

from apps.finance.api import ObligationCreateView

from . import api

urlpatterns = [
    path("dashboard", api.DashboardView.as_view()),
    path("forecast", api.ForecastView.as_view()),
    path("simulate", api.SimulateView.as_view()),
    path("calendar", api.CalendarView.as_view()),
    path("obligations", ObligationCreateView.as_view()),
]
