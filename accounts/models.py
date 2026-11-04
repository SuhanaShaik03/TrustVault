from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "admin", "Administrator"
        OWNER = "owner", "Owner"
        VIEWER = "viewer", "Viewer"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.VIEWER)
    is_approved = models.BooleanField(default=False)

    @property
    def display_name(self):
        return self.get_full_name().strip() or self.username

    def save(self, *args, **kwargs):
        if self.is_superuser:
            self.role = self.Role.ADMIN
            self.is_approved = True
        super().save(*args, **kwargs)


class AdminInvitation(models.Model):
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="created_admin_invitations",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(default=timezone.now)
    used_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Administrator invitation created {self.created_at:%Y-%m-%d}"


class LoginAccessRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DECLINED = "declined", "Declined"

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="login_requests",
        null=True,
        blank=True,
    )
    username_snapshot = models.CharField(max_length=150)
    name_snapshot = models.CharField(max_length=302)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    requested_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        related_name="reviewed_login_requests",
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-requested_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(status="pending", user__isnull=False),
                name="one_pending_login_request_per_user",
            )
        ]

    def __str__(self):
        return f"{self.username_snapshot} - {self.get_status_display()}"
