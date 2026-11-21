from django.urls import path

from . import api

urlpatterns = [
    path("actions", api.ActionCreateView.as_view()),
    path("actions/<int:plan_id>/approve", api.ActionApproveView.as_view()),
    path("reminders", api.RemindersView.as_view()),
]
