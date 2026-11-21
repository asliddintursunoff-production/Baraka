from django.urls import path

from . import api, dev_views

urlpatterns = [
    path("sources", api.SourcesView.as_view()),
    path("sources/confirm", api.confirm),
    path("sources/sync", api.sync_now),
    path("sources/<int:source_id>/remap", api.RemapView.as_view()),
    path("sources/issues/<int:issue_id>/resolve", api.IssueResolveView.as_view()),
    # DEBUG only (404 otherwise): demo export through a FakeReader
    path("dev/sources/demo", dev_views.connect_demo),
    path("dev/sources/demo/add-expense", dev_views.add_expense),
]
