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

from .gate import require_data, status_payload
from .middleware import SESSION_KEY
from .models import Business, Membership


class BusinessAPIView(APIView):
    """Base for every tenant API: authenticated + a current business from the session."""

    permission_classes = [IsAuthenticated]
    requires_data = False  # True: 409 {"code": "no_data"} until a source is confirmed + synced

    def initial(self, request: Request, *args: Any, **kwargs: Any) -> None:
        super().initial(request, *args, **kwargs)
        b = getattr(request._request, "business", None)
        if b is None:
            raise PermissionDenied("Sizga biznes biriktirilmagan.")
        if self.requires_data:
            require_data(b)

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
        else {
            "id": current.pk,
            "name": current.name,
            "city": current.city,
            "is_demo": current.is_demo,
        },
        "businesses": [
            {
                "id": m.business_id,
                "name": m.business.name,
                "city": m.business.city,
                "role": m.role,
                "is_demo": m.business.is_demo,
            }
            for m in memberships
        ],
        **status_payload(current),
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


def _err(code: str, message: str) -> Response:
    return Response({"error": code, "message": message}, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(APIView):
    """Creates the user + an EMPTY business (no seed data) and logs in."""

    permission_classes = [AllowAny]

    def post(self, request: Request) -> Response:
        from django.contrib.auth import get_user_model
        from django.core.exceptions import ValidationError
        from django.core.validators import validate_email
        from django.db import transaction

        data = request.data if isinstance(request.data, dict) else {}
        email = str(data.get("email", "")).strip().lower()[:150]
        password = str(data.get("password", ""))
        first = str(data.get("first_name", "")).strip()[:60]
        try:
            validate_email(email)
        except ValidationError:
            return _err("invalid", "Email noto'g'ri.")
        if len(password) < 8:
            return _err("weak_password", "Parol kamida 8 ta belgidan iborat bo'lsin.")
        if not data.get("accept_terms"):
            return _err("terms_required", "Foydalanish shartlariga rozilik bildiring.")
        User = get_user_model()
        if User.objects.filter(username=email).exists():
            return _err(
                "email_taken", "Bu email bilan hisob allaqachon bor. Kirish sahifasidan kiring."
            )
        with transaction.atomic():
            user = User.objects.create_user(
                username=email, email=email, password=password, first_name=first
            )
            b = Business.objects.create(name=first or "Mening biznesim", profile_completed=False)
            Membership.objects.create(user=user, business=b, role=Membership.Role.OWNER)
        login(request._request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session[SESSION_KEY] = b.pk
        return Response(me_payload(user, b), status=status.HTTP_201_CREATED)


class OnboardingBusinessView(BusinessAPIView):
    """Step 1: business profile (name, kind, city, staff, salary day, safe minimum)."""

    def post(self, request: Request) -> Response:
        from decimal import Decimal

        from apps.ingestion.normalize import parse_amount

        data = request.data if isinstance(request.data, dict) else {}
        b = self.business
        if b.is_demo:
            return _err("invalid", "Demo biznesni o'zgartirib bo'lmaydi.")
        name = str(data.get("name", "")).strip()[:120]
        kind = str(data.get("kind", "cafe"))
        try:
            staff = int(data.get("staff_count") or 0)
            day = int(data.get("salary_day") or 0)
        except (TypeError, ValueError):
            return _err("invalid", "Xodimlar soni va oylik kuni raqam bo'lsin.")
        if not name:
            return _err("invalid", "Biznes nomini yozing.")
        if kind not in Business.Kind.values or not 0 <= staff <= 10_000 or not 1 <= day <= 31:
            return _err(
                "invalid", "Turi, xodimlar soni (0–10 000) va oylik kuni (1–31) to'g'ri bo'lsin."
            )
        safe = (
            parse_amount(data.get("safe_min")) if data.get("safe_min") not in (None, "") else None
        )
        if safe is not None and safe < Decimal(0):
            return _err("invalid", "Kassadagi minimum manfiy bo'lmaydi.")
        b.name, b.kind, b.city = name, kind, str(data.get("city") or "Toshkent")[:64]
        b.staff_count, b.salary_day, b.profile_completed = staff or None, day, True
        if safe is not None:
            b.safe_min_balance = safe
        b.save()
        return Response(me_payload(request.user, b))


class DemoStartView(APIView):
    """'Demo kafe bilan sinab ko'rish': the user's own separate demo business."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request) -> Response:
        from apps.finance.demo_clone import demo_business_for

        b = demo_business_for(request.user)
        request.session[SESSION_KEY] = b.pk
        return Response(me_payload(request.user, b))
