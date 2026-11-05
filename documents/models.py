import uuid
from pathlib import Path

from django.conf import settings
from django.db import models

from documents.storage import PrivateDocumentStorage
from documents.validators import validate_document_file


def document_upload_path(_instance, filename):
    extension = Path(filename).suffix.lower()
    return f"documents/{uuid.uuid4().hex}{extension}"


def change_request_upload_path(_instance, filename):
    extension = Path(filename).suffix.lower()
    return f"pending_changes/{uuid.uuid4().hex}{extension}"


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="owned_documents",
    )
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    file = models.FileField(
        storage=PrivateDocumentStorage(),
        upload_to=document_upload_path,
        validators=[validate_document_file],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return self.title


class DocumentGrant(models.Model):
    class Permission(models.TextChoices):
        READ = "read", "View"
        EDIT = "edit", "Edit (submit for approval)"

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name="grants")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_grants",
    )
    permission = models.CharField(max_length=4, choices=Permission.choices, default=Permission.READ)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["document", "user"], name="unique_document_grant")
        ]

    def __str__(self):
        return f"{self.user} - {self.document} ({self.permission})"


class DocumentChangeRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="change_requests",
    )
    viewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="document_change_requests",
    )
    submitted_file = models.FileField(
        storage=PrivateDocumentStorage(),
        upload_to=change_request_upload_path,
        validators=[validate_document_file],
        blank=True,
    )
    uploaded_filename = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="reviewed_document_change_requests",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["document", "viewer"],
                condition=models.Q(status="pending"),
                name="one_pending_document_change_per_viewer",
            )
        ]

    def __str__(self):
        return f"{self.viewer} - {self.document} ({self.get_status_display()})"


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    document = models.ForeignKey(
        Document,
        on_delete=models.SET_NULL,
        related_name="audit_events",
        null=True,
        blank=True,
    )
    action = models.CharField(max_length=40)
    target_label = models.CharField(max_length=255, blank=True)
    details = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    actor_reference = models.CharField(max_length=150, blank=True)
    document_reference = models.CharField(max_length=36, blank=True)
    created_at = models.DateTimeField()
    previous_hash = models.CharField(max_length=64)
    event_hash = models.CharField(max_length=64, unique=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.action} - {self.target_label}"
