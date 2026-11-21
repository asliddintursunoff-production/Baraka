from django.urls import include, path, re_path

from . import views

urlpatterns = [
    path("api/health", views.health, name="health"),
    path("app-config.js", views.app_config_js, name="app-config-js"),
    path("api/", include("apps.tenancy.urls")),
    path("api/", include("apps.insights.urls")),
    path("api/", include("apps.actions.urls")),
    path("api/", include("apps.ai.urls")),
    path("api/", include("apps.telemetry.urls")),
    # Everything that is not the API is the React app (client-side routing).
    re_path(r"^(?!api/|static/).*$", views.spa, name="spa"),
]
