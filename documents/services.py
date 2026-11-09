import hashlib
import ipaddress
import json

from django.conf import settings
from django.db import connection, transaction
from django.utils import timezone

from documents.models import AuditEvent, Document, DocumentChangeRequest


GENESIS_HASH = "0" * 64


def _request_ip_address(request):
    trusted_proxy_count = settings.TRUSTED_PROXY_COUNT
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if trusted_proxy_count and forwarded_for:
        forwarded_addresses = [address.strip() for address in forwarded_for.split(",")]
        if len(forwarded_addresses) >= trusted_proxy_count:
            candidate = forwarded_addresses[-trusted_proxy_count]
            try:
                return str(ipaddress.ip_address(candidate))
            except ValueError:
                pass

    remote_addr = request.META.get("REMOTE_ADDR")
    if not remote_addr:
        return None
    try:
        return str(ipaddress.ip_address(remote_addr))
    except ValueError as error:
        raise ValueError("The request has an invalid remote IP address.") from error


def _event_hash(
    previous_hash,
    actor_reference,
    document_reference,
    action,
    target_label,
    details,
    created_at,
    ip_address=None,
):
    payload = {
        "action": action,
        "actor_reference": actor_reference,
        "created_at": created_at.isoformat(),
        "details": details,
        "document_reference": document_reference,
        "previous_hash": previous_hash,
        "target_label": target_label,
    }
    if ip_address:
        payload["ip_address"] = ip_address
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@transaction.atomic
def record_event(
    *,
    actor,
    action,
    target_label="",
    document=None,
    details=None,
    request=None,
):
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [0x545255535456])
    previous = AuditEvent.objects.select_for_update().order_by("-id").first()
    previous_hash = previous.event_hash if previous else GENESIS_HASH
    created_at = timezone.now()
    payload_details = details or {}
    actor_reference = str(actor.pk) if actor else ""
    document_reference = str(document.pk) if document else ""
    ip_address = None
    if request is not None:
        ip_address = _request_ip_address(request)
    event_hash = _event_hash(
        previous_hash,
        actor_reference,
        document_reference,
        action,
        target_label,
        payload_details,
        created_at,
        ip_address,
    )
    return AuditEvent.objects.create(
        actor=actor,
        document=document,
        action=action,
        target_label=target_label,
        details=payload_details,
        ip_address=ip_address,
        actor_reference=actor_reference,
        document_reference=document_reference,
        created_at=created_at,
        previous_hash=previous_hash,
        event_hash=event_hash,
    )


def verify_audit_chain():
    previous_hash = GENESIS_HASH
    for event in AuditEvent.objects.order_by("id"):
        expected = _event_hash(
            previous_hash,
            event.actor_reference,
            event.document_reference,
            event.action,
            event.target_label,
            event.details,
            event.created_at,
            event.ip_address,
        )
        if event.previous_hash != previous_hash or event.event_hash != expected:
            return False
        previous_hash = event.event_hash
    return True


@transaction.atomic
def review_document_change(change_request, owner, approve, request=None):
    change_request = (
        DocumentChangeRequest.objects.select_for_update()
        .select_related("document", "viewer")
        .get(pk=change_request.pk)
    )
    if (
        change_request.status != DocumentChangeRequest.Status.PENDING
        or change_request.document.owner_id != owner.pk
    ):
        return False

    document = Document.objects.select_for_update().get(pk=change_request.document_id)
    submitted_file = change_request.submitted_file.name
    submitted_storage = change_request.submitted_file.storage
    old_file = document.file.name
    now = timezone.now()
    change_request.status = (
        DocumentChangeRequest.Status.APPROVED
        if approve
        else DocumentChangeRequest.Status.DECLINED
    )
    change_request.reviewed_by = owner
    change_request.reviewed_at = now

    if approve:
        document.file.name = submitted_file
        document.save(update_fields=["file", "updated_at"])
        submitted_storage.delete(old_file)
    else:
        change_request.submitted_file = ""
        submitted_storage.delete(submitted_file)

    change_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "submitted_file"])
    record_event(
        actor=owner,
        action="document_change_approved" if approve else "document_change_declined",
        target_label=document.title,
        document=document,
        details={
            "request_id": change_request.pk,
            "viewer": change_request.viewer.username,
        },
        request=request,
    )
    return True
