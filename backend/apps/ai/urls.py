from django.urls import path

from . import dev_views

urlpatterns = [
    # M0 voice spike (DEBUG only). Replaced by /api/live/session + /api/tools/<name> in M3/M4.
    path("dev/live/session", dev_views.dev_live_session, name="dev-live-session"),
    path("dev/tools/<str:name>", dev_views.dev_tool, name="dev-tool"),
]
