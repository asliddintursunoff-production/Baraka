"""Session auth (email + password), current user/business, business switcher."""

from __future__ import annotations

from typing import Any

from django.contrib.auth import authenticate, login, logout
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from .middleware import SESSION_KEY
from .models import Business, Membership


class BusinessAPIView(APIView):
    """Base for every tenant API: authenticated + a current business from the session."""

    permission_classes = [IsAuthenticated]

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        if getattr(request._request, "business", None) is None:
            raise PermissionDenied("Sizga biznes biriktirilmagan.")

    @property
    def business(self) -> Business:
        b: Business = self.request._request.business  # type: ignore[attr-defined]
        return b


def me_payload(user: Any, current: Business | None) -> dict[str, Any]:
    memberships = (
        Membership.objects.filter(user=user).select_related("business").order_by("created_at", "id")
    )
    return {
        "user": {"email": user.email, "first_name": user.first_name, "last_name": user.last_name},
        "business": None
        if current is None
        else {"id": current.pk, "name": current.name, "city": current.city},
        "businesses": [
            {"id": m.business_id, "name": m.business.name, "city": m.business.city, "role": m.role}
            for m in memberships
        ],
    }


class LoginSerializer(serializers.Serializer[dict[str, str]]):
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128)


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = authenticate(
            request._request,
            username=s.validated_data["email"].lower(),
            password=s.validated_data["password"],
        )
        if user is None:
            return Response(
                {"error": "invalid_credentials", "message": "Email yoki parol noto'g'ri."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        login(request._request, user)
        first = Membership.objects.filter(user=user).order_by("created_at", "id").first()
        if first:
            request.session[SESSION_KEY] = first.business_id
        return Response(me_payload(user, first.business if first else None))


class LogoutView(APIView):
    def post(self, request: Request) -> Response:
        logout(request._request)
        return Response({"ok": True})


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request) -> Response:
        return Response(me_payload(request.user, getattr(request._request, "business", None)))


class SwitchBusinessView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        data = request.data if isinstance(request.data, dict) else {}
        try:
            bid = int(data.get("business_id", ""))
        except (TypeError, ValueError):
            return Response({"error": "business_id_required"}, status=400)
        m = (
            Membership.objects.filter(user_id=int(request.user.pk or 0), business_id=bid)
            .select_related("business")
            .first()
        )
        if m is None:
            raise PermissionDenied("Bu biznesga ruxsatingiz yo'q.")
        request.session[SESSION_KEY] = bid
        return Response(me_payload(request.user, m.business))
