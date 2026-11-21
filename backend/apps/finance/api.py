"""Manual payments ("+ To'lov qo'shish" on the calendar)."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.response import Response

from apps.actions.audit import audit
from apps.insights.forecasting import refresh_forecast
from apps.tenancy.api import BusinessAPIView
from apps.tenancy.context import today_for

from .models import Obligation


class ObligationIn(serializers.Serializer[dict[str, object]]):
    title = serializers.CharField(max_length=160)
    amount = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("1"))
    due_date = serializers.DateField()
    priority = serializers.ChoiceField(choices=Obligation.Priority.choices)
    category = serializers.CharField(max_length=32, required=False, allow_blank=True)


class ObligationCreateView(BusinessAPIView):
    def post(self, request: Request) -> Response:
        s = ObligationIn(data=request.data)
        s.is_valid(raise_exception=True)
        data = s.validated_data
        if data["due_date"] < today_for(self.business):
            return Response(
                {"error": "past_date", "message": "O'tgan sanaga to'lov qo'shib bo'lmaydi."},
                status=400,
            )
        ob = Obligation.objects.create(
            business=self.business,
            title=data["title"],
            amount=data["amount"],
            due_date=data["due_date"],
            priority=data["priority"],
            category=data.get("category", ""),
            source=Obligation.Source.MANUAL,
        )
        audit(
            f"user:{request.user.pk}",
            "obligation_created",
            args={"id": ob.pk, "amount": str(ob.amount)},
        )
        refresh_forecast(self.business)
        return Response({"ok": True, "id": ob.pk}, status=201)
