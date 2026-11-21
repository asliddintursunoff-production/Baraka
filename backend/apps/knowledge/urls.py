from django.urls import path

from . import api

urlpatterns = [
    path("knowledge/candidates/<int:candidate_id>/accept", api.CandidateAcceptView.as_view()),
    path("knowledge/candidates/<int:candidate_id>/reject", api.CandidateRejectView.as_view()),
]
