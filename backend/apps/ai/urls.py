from django.urls import path

from . import dev_views, live_api, views

urlpatterns = [
    path("chat/bootstrap", views.ChatBootstrapView.as_view()),
    path("chat/messages", views.chat_messages),
    path("chat/conversations/<int:conv_id>", views.ConversationView.as_view()),
    path("chat/messages/<int:message_id>/speech", views.ChatSpeechView.as_view()),
    path("chat/transcribe", views.transcribe),
    path("tools/<str:name>", views.ToolView.as_view()),
    path("live/session", live_api.LiveSessionView.as_view()),
    path("live/session/prefetch", live_api.LiveSessionView.as_view()),
    path("live/finish", live_api.LiveFinishView.as_view()),
    # M0 voice spike (DEBUG only).
    path("dev/live/session", dev_views.dev_live_session, name="dev-live-session"),
    path("dev/tools/<str:name>", dev_views.dev_tool, name="dev-tool"),
]
