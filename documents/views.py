from functools import wraps
from mimetypes import guess_type
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.models import User
from documents.forms import (
    DocumentChangeRequestForm,
    DocumentEditForm,
    DocumentForm,
    GrantActionForm,
    GrantForm,
)
from documents.models import Document, DocumentChangeRequest, DocumentGrant
from documents.services import record_event, review_document_change


def owner_required(view_func):
    @wraps(view_func)
    @login_required
    def wrapped(request, *args, **kwargs):
        if request.user.role != User.Role.OWNER:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


def get_document_access(request, document_id, edit=False):
    user = request.user
    document = get_object_or_404(Document, pk=document_id)
    if document.owner_id == user.pk:
        return document
    permission = DocumentGrant.objects.filter(document=document, user=user).values_list(
        "permission", flat=True
    ).first()
    if permission is None or (edit and permission != DocumentGrant.Permission.EDIT):
        if user.is_authenticated:
            record_event(
                actor=user,
                action="document_access_denied",
                target_label=document.title,
                document=document,
                details={"edit": edit},
                request=request,
            )
        raise Http404
    return document


@login_required
def document_list(request):
    if request.user.role == User.Role.OWNER:
        section = request.GET.get("section", "documents")
        if section not in {"documents", "login-details", "approval-requests"}:
            section = "documents"
        context = {
            "section": section,
            "own_documents": Document.objects.filter(owner=request.user).order_by("-created_at"),
            "pending_change_count": DocumentChangeRequest.objects.filter(
                document__owner=request.user,
                status=DocumentChangeRequest.Status.PENDING,
            ).count(),
        }
        if section == "login-details":
            login_list = request.GET.get("list", "viewers")
            if login_list not in {"viewers", "owners"}:
                login_list = "viewers"
            context["login_list"] = login_list
            context.update(
                {
                    "viewers": User.objects.filter(
                        role=User.Role.VIEWER,
                        is_active=True,
                    ).order_by("username"),
                    "other_owners": User.objects.filter(
                        role=User.Role.OWNER,
                        is_active=True,
                    ).exclude(pk=request.user.pk).order_by("username"),
                }
            )
        elif section == "approval-requests":
            context["pending_change_requests"] = (
                DocumentChangeRequest.objects.filter(
                    document__owner=request.user,
                    status=DocumentChangeRequest.Status.PENDING,
                )
                .select_related("document", "viewer")
                .order_by("created_at")
            )
        return render(request, "documents/owner_dashboard.html", context)

    viewer_tab = request.GET.get("tab", "assigned")
    if viewer_tab not in {"assigned", "uploaded"}:
        viewer_tab = "assigned"
    return render(
        request,
        "documents/document_list.html",
        {
            "viewer_tab": viewer_tab,
            "document_grants": DocumentGrant.objects.filter(
                user=request.user
            ).select_related("document", "document__owner"),
            "change_requests": DocumentChangeRequest.objects.filter(viewer=request.user)
            .select_related("document")
            .order_by("-created_at"),
        },
    )


@owner_required
def document_upload(request):
    form = DocumentForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        document = form.save(commit=False)
        document.owner = request.user
        document.save()
        record_event(
            actor=request.user,
            action="document_uploaded",
            target_label=document.title,
            document=document,
            request=request,
        )
        messages.success(request, "Document uploaded.")
        return redirect("documents:document_detail", document_id=document.pk)
    return render(request, "documents/document_form.html", {"form": form, "heading": "Upload document"})


@login_required
def document_detail(request, document_id):
    document = get_document_access(request, document_id)
    record_event(
        actor=request.user,
        action="document_received",
        target_label=document.title,
        document=document,
        request=request,
    )
    grants = document.grants.select_related("user").all() if document.owner_id == request.user.pk else []
    is_owner = document.owner_id == request.user.pk
    can_submit_change = not is_owner and DocumentGrant.objects.filter(
        document=document,
        user=request.user,
        permission=DocumentGrant.Permission.EDIT,
    ).exists()
    viewer_change_request = None
    if not is_owner:
        viewer_change_request = document.change_requests.filter(viewer=request.user).first()
    return render(
        request,
        "documents/document_detail.html",
        {
            "document": document,
            "grants": grants,
            "is_owner": is_owner,
            "can_submit_change": can_submit_change,
            "viewer_change_request": viewer_change_request,
        },
    )


@login_required
def document_download(request, document_id):
    document = get_document_access(request, document_id)
    record_event(
        actor=request.user,
        action="document_downloaded",
        target_label=document.title,
        document=document,
        request=request,
    )
    return FileResponse(
        document.file.open("rb"),
        as_attachment=True,
        filename=document.file.name.rsplit("/", 1)[-1],
    )


@login_required
def document_open(request, document_id):
    document = get_document_access(request, document_id)
    record_event(
        actor=request.user,
        action="document_opened",
        target_label=document.title,
        document=document,
        request=request,
    )
    filename = Path(document.file.name).name
    content_type = guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(
        document.file.open("rb"),
        as_attachment=False,
        filename=filename,
        content_type=content_type,
    )


@login_required
def document_edit(request, document_id):
    document = get_document_access(request, document_id, edit=True)
    if document.owner_id != request.user.pk:
        raise Http404
    previous_file = document.file.name
    form = DocumentEditForm(request.POST or None, request.FILES or None, instance=document)
    if request.method == "POST" and form.is_valid():
        storage = document.file.storage
        document = form.save()
        file_replaced = document.file.name != previous_file
        if file_replaced:
            storage.delete(previous_file)
        record_event(
            actor=request.user,
            action="document_modified",
            target_label=document.title,
            document=document,
            details={"file_replaced": file_replaced},
            request=request,
        )
        messages.success(request, "Document details updated.")
        return redirect("documents:document_detail", document_id=document.pk)
    return render(request, "documents/document_form.html", {"form": form, "heading": "Edit document"})


@login_required
def document_change_submit(request, document_id):
    document = get_document_access(request, document_id, edit=True)
    if document.owner_id == request.user.pk:
        return redirect("documents:document_edit", document_id=document.pk)

    pending_request = document.change_requests.filter(
        viewer=request.user,
        status=DocumentChangeRequest.Status.PENDING,
    ).first()
    if pending_request:
        messages.info(request, "You already have a document change awaiting owner approval.")
        return redirect("documents:document_detail", document_id=document.pk)

    form = DocumentChangeRequestForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        change_request = form.save(commit=False)
        change_request.document = document
        change_request.viewer = request.user
        change_request.uploaded_filename = request.FILES["submitted_file"].name
        change_request.save()
        record_event(
            actor=request.user,
            action="document_change_submitted",
            target_label=document.title,
            document=document,
            details={"request_id": change_request.pk},
            request=request,
        )
        messages.success(request, "Your modified document was sent to the owner for approval.")
        return redirect("documents:document_detail", document_id=document.pk)
    return render(
        request,
        "documents/document_form.html",
        {
            "form": form,
            "heading": f"Submit a modified version of {document.title}",
            "help_text": (
                "The current document will not change until its owner approves your upload."
            ),
        },
    )


@owner_required
def owner_viewer_access(request, viewer_id):
    viewer = get_object_or_404(
        User,
        pk=viewer_id,
        role=User.Role.VIEWER,
        is_active=True,
    )
    if request.method == "POST":
        form = GrantActionForm(request.POST)
        if form.is_valid():
            document = get_object_or_404(
                Document,
                pk=form.cleaned_data["document_id"],
                owner=request.user,
            )
            action = form.cleaned_data["action"]
            grant = DocumentGrant.objects.filter(document=document, user=viewer).first()
            if action == "revoke":
                if grant:
                    grant.delete()
                    record_event(
                        actor=request.user,
                        action="document_access_revoked",
                        target_label=document.title,
                        document=document,
                        details={"recipient": viewer.username},
                        request=request,
                    )
                    messages.success(request, f"Access for {viewer.username} was revoked.")
                else:
                    messages.info(request, f"{viewer.username} did not have this document.")
            else:
                was_created = grant is None
                previous_permission = grant.permission if grant else None
                grant, _ = DocumentGrant.objects.update_or_create(
                    document=document,
                    user=viewer,
                    defaults={"permission": action},
                )
                if was_created or previous_permission != action:
                    record_event(
                        actor=request.user,
                        action="document_shared" if was_created else "document_permission_updated",
                        target_label=document.title,
                        document=document,
                        details={
                            "recipient": viewer.username,
                            "permission": action,
                        },
                        request=request,
                    )
                messages.success(
                    request,
                    f"{viewer.username} now has {grant.get_permission_display().lower()} access.",
                )
            return redirect("documents:owner_viewer_access", viewer_id=viewer.pk)
    else:
        form = GrantActionForm()

    grants = {
        grant.document_id: grant
        for grant in DocumentGrant.objects.filter(
            user=viewer,
            document__owner=request.user,
        )
    }
    document_access = [
        {"document": document, "grant": grants.get(document.pk)}
        for document in Document.objects.filter(owner=request.user)
    ]
    return render(
        request,
        "documents/owner_viewer_access.html",
        {
            "viewer": viewer,
            "document_access": document_access,
            "action_form": form,
        },
    )


@owner_required
def document_change_detail(request, request_id):
    change_request = get_object_or_404(
        DocumentChangeRequest.objects.select_related("document", "viewer"),
        pk=request_id,
        document__owner=request.user,
    )
    if request.method == "POST":
        decision = request.POST.get("decision")
        if decision not in {"approve", "decline"}:
            raise PermissionDenied("Invalid document change decision.")
        changed = review_document_change(
            change_request,
            request.user,
            approve=decision == "approve",
            request=request,
        )
        if changed:
            messages.success(
                request,
                "The viewer's document was approved and replaced."
                if decision == "approve"
                else "The viewer's document change was declined.",
            )
        else:
            messages.info(request, "This document change was already reviewed.")
        return redirect(
            f"{reverse('documents:document_list')}?section=approval-requests"
        )
    if change_request.status != DocumentChangeRequest.Status.PENDING:
        raise Http404
    return render(
        request,
        "documents/document_change_detail.html",
        {"change_request": change_request},
    )


@owner_required
def document_change_preview(request, request_id):
    change_request = get_object_or_404(
        DocumentChangeRequest.objects.select_related("document"),
        pk=request_id,
        document__owner=request.user,
        status=DocumentChangeRequest.Status.PENDING,
    )
    filename = Path(change_request.submitted_file.name).name
    content_type = guess_type(filename)[0] or "application/octet-stream"
    return FileResponse(
        change_request.submitted_file.open("rb"),
        as_attachment=False,
        filename=filename,
        content_type=content_type,
    )


@owner_required
@require_POST
def document_delete(request, document_id):
    document = get_object_or_404(Document, pk=document_id, owner=request.user)
    record_event(
        actor=request.user,
        action="document_deleted",
        target_label=document.title,
        details={"document_id": str(document.pk)},
        request=request,
    )
    files_to_delete = [(document.file.storage, document.file.name)]
    files_to_delete.extend(
        (change_request.submitted_file.storage, change_request.submitted_file.name)
        for change_request in document.change_requests.all()
        if change_request.submitted_file
    )
    document.delete()
    for storage, file_name in files_to_delete:
        storage.delete(file_name)
    messages.success(request, "Document deleted.")
    return redirect("documents:document_list")


@owner_required
def document_share(request, document_id):
    document = get_object_or_404(Document, pk=document_id, owner=request.user)
    form = GrantForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        grant = form.save(commit=False)
        grant.document = document
        if grant.user_id == request.user.pk:
            form.add_error("user", "You already own this document.")
        elif DocumentGrant.objects.filter(document=document, user=grant.user).exists():
            form.add_error("user", "This user already has access.")
        else:
            grant.save()
            record_event(
                actor=request.user,
                action="document_shared",
                target_label=document.title,
                document=document,
                details={
                    "recipient": grant.user.username,
                    "permission": grant.permission,
                },
                request=request,
            )
            messages.success(request, "Document access granted.")
            return redirect("documents:document_detail", document_id=document.pk)
    return render(
        request,
        "documents/document_form.html",
        {"form": form, "heading": f"Share {document.title}"},
    )


@owner_required
@require_POST
def document_revoke(request, document_id, grant_id):
    document = get_object_or_404(Document, pk=document_id, owner=request.user)
    grant = get_object_or_404(DocumentGrant, pk=grant_id, document=document)
    recipient = grant.user.username
    record_event(
        actor=request.user,
        action="document_access_revoked",
        target_label=document.title,
        document=document,
        details={"recipient": recipient},
        request=request,
    )
    grant.delete()
    messages.success(request, f"Access for {recipient} was revoked.")
    return redirect("documents:document_detail", document_id=document.pk)
