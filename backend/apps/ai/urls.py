from django.http import HttpRequest, HttpResponse
from django.urls import path

from . import dev_views, views


def live_prefetch(request: HttpRequest) -> HttpResponse:
    """M4 fills this (token prefetch on hover). Harmless no-op until then."""
    return HttpResponse(status=204)


urlpatterns = [
    path("chat/bootstrap", views.ChatBootstrapView.as_view()),
    path("chat/messages", views.chat_messages),
    path("chat/messages/<int:message_id>/speech", views.ChatSpeechView.as_view()),
    path("chat/transcribe", views.transcribe),
    path("tools/<str:name>", views.ToolView.as_view()),
    path("live/session/prefetch", live_prefetch),
    # M0 voice spike (DEBUG only).
    path("dev/live/session", dev_views.dev_live_session, name="dev-live-session"),
    path("dev/tools/<str:name>", dev_views.dev_tool, name="dev-tool"),
]
