from __future__ import annotations

from rest_framework.request import Request
from rest_framework.response import Response

from apps.actions.audit import audit
from apps.tenancy.api import BusinessAPIView

from .learning import accept_candidate
from .models import RuleCandidate


class CandidateAcceptView(BusinessAPIView):
    def post(self, request: Request, candidate_id: int) -> Response:
        if not RuleCandidate.objects.filter(pk=candidate_id).exists():
            return Response({"error": "not_found"}, status=404)
        rule = accept_candidate(self.business, candidate_id, request.user.pk)
        return Response({"rule_id": rule.pk, "text_uz": rule.text_uz, "forecast_changed": True})


class CandidateRejectView(BusinessAPIView):
    def post(self, request: Request, candidate_id: int) -> Response:
        n = RuleCandidate.objects.filter(
            pk=candidate_id, status=RuleCandidate.Status.PENDING
        ).update(status=RuleCandidate.Status.REJECTED)
        if n:
            audit(f"user:{request.user.pk}", "rule_rejected", args={"candidate_id": candidate_id})
        return Response({"ok": True})
