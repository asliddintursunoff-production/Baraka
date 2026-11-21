from django.urls import path

from . import api

urlpatterns = [
    path("knowledge", api.KnowledgeView.as_view()),
    path("knowledge/rules", api.RuleCreateView.as_view()),
    path("knowledge/rules/<int:rule_id>/toggle", api.RuleToggleView.as_view()),
    path("knowledge/candidates/<int:candidate_id>/accept", api.CandidateAcceptView.as_view()),
    path("knowledge/candidates/<int:candidate_id>/reject", api.CandidateRejectView.as_view()),
]
