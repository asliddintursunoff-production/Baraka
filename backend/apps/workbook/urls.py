from django.urls import path

from . import api

urlpatterns = [
    path("files", api.FilesView.as_view()),
    path("files/<str:file_id>", api.FileDetailView.as_view()),
    path("files/<str:file_id>/ask", api.FileAskView.as_view()),
]
