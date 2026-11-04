from django.urls import path

from documents import views

app_name = "documents"

urlpatterns = [
    path("documents/", views.document_list, name="document_list"),
    path(
        "owner/viewers/<int:viewer_id>/",
        views.owner_viewer_access,
        name="owner_viewer_access",
    ),
    path(
        "owner/approval-requests/<int:request_id>/",
        views.document_change_detail,
        name="document_change_detail",
    ),
    path(
        "owner/approval-requests/<int:request_id>/document/",
        views.document_change_preview,
        name="document_change_preview",
    ),
    path("documents/upload/", views.document_upload, name="document_upload"),
    path("documents/<uuid:document_id>/", views.document_detail, name="document_detail"),
    path(
        "documents/<uuid:document_id>/download/",
        views.document_download,
        name="document_download",
    ),
    path(
        "documents/<uuid:document_id>/open/",
        views.document_open,
        name="document_open",
    ),
    path("documents/<uuid:document_id>/edit/", views.document_edit, name="document_edit"),
    path(
        "documents/<uuid:document_id>/submit-change/",
        views.document_change_submit,
        name="document_change_submit",
    ),
    path("documents/<uuid:document_id>/delete/", views.document_delete, name="document_delete"),
    path("documents/<uuid:document_id>/share/", views.document_share, name="document_share"),
    path(
        "documents/<uuid:document_id>/revoke/<int:grant_id>/",
        views.document_revoke,
        name="document_revoke",
    ),
]
