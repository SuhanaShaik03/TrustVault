import hashlib
import secrets

from django.db import transaction
from django.utils import timezone

from accounts.models import AdminInvitation, LoginAccessRequest, User


def _admin_invitation_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_admin_invitation(admin):
    token = secrets.token_urlsafe(32)
    invitation = AdminInvitation.objects.create(
        token_hash=_admin_invitation_hash(token),
        created_by=admin,
    )
    return token, invitation


def has_valid_admin_invitation(token):
    if not token:
        return False
    return AdminInvitation.objects.filter(
        token_hash=_admin_invitation_hash(token),
        used_at__isnull=True,
    ).exists()


@transaction.atomic
def consume_admin_invitation(token):
    if not token:
        return False
    return (
        AdminInvitation.objects.filter(
            token_hash=_admin_invitation_hash(token),
            used_at__isnull=True,
        ).update(used_at=timezone.now())
        == 1
    )


@transaction.atomic
def request_login_access(user):
    pending = LoginAccessRequest.objects.filter(
        user=user,
        status=LoginAccessRequest.Status.PENDING,
    ).first()
    if pending:
        return pending, False

    latest = LoginAccessRequest.objects.filter(user=user).first()
    request = LoginAccessRequest.objects.create(
        user=user,
        username_snapshot=user.username,
        name_snapshot=user.display_name,
    )
    return request, bool(latest and latest.status == LoginAccessRequest.Status.DECLINED)


@transaction.atomic
def review_login_request(login_request, admin, approve):
    login_request = LoginAccessRequest.objects.select_for_update().get(pk=login_request.pk)
    if login_request.status != LoginAccessRequest.Status.PENDING:
        return False

    login_request.status = (
        LoginAccessRequest.Status.APPROVED if approve else LoginAccessRequest.Status.DECLINED
    )
    login_request.reviewed_by = admin
    login_request.reviewed_at = timezone.now()
    login_request.save(update_fields=["status", "reviewed_by", "reviewed_at"])

    if login_request.user_id and approve:
        User.objects.filter(pk=login_request.user_id).update(is_approved=True)
    return True
