from functools import wraps

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.forms import LoginForm, RegistrationForm, UserCreateForm
from accounts.models import LoginAccessRequest, User
from accounts.services import (
    consume_admin_invitation,
    create_admin_invitation,
    request_login_access,
    review_login_request,
)
from documents.models import AuditEvent, DocumentChangeRequest, DocumentGrant
from documents.services import record_event, verify_audit_chain
from documents.storage import check_private_storage


def administrator_required(view_func):
    @wraps(view_func)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("accounts:login")
        if request.user.role != User.Role.ADMIN:
            raise PermissionDenied
        return view_func(request, *args, **kwargs)

    return wrapped


def dashboard(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    if request.user.role == User.Role.ADMIN:
        return redirect("accounts:admin_dashboard")
    return redirect("documents:document_list")


def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = LoginForm(request=request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.get_user()
        if user.is_approved:
            login(request, user)
            return redirect("accounts:dashboard")

        access_request, was_declined = request_login_access(user)
        if not access_request.pk:
            raise RuntimeError("The login access request was not saved.")
        record_event(
            actor=user,
            action="login_requested",
            target_label=user.username,
            details={"request_id": access_request.pk},
            request=request,
        )
        return render(
            request,
            "accounts/login_status.html",
            {"was_declined": was_declined},
            status=403 if was_declined else 200,
        )
    return render(request, "accounts/login.html", {"form": form})


def register_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    form = RegistrationForm(
        request.POST or None,
        initial={"invitation": request.GET.get("invite", "")},
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            role = form.cleaned_data["role"]
            if role == User.Role.ADMIN and not consume_admin_invitation(
                form.cleaned_data["invitation"]
            ):
                form.add_error(
                    None,
                    "This administrator invitation is invalid or has already been used.",
                )
                return render(request, "accounts/register.html", {"form": form})
            user = form.save(commit=False)
            user.is_approved = role == User.Role.ADMIN
            user.save()
            if role != User.Role.ADMIN:
                LoginAccessRequest.objects.create(
                    user=user,
                    username_snapshot=user.username,
                    name_snapshot=user.display_name,
                )
            record_event(
                actor=user,
                action="account_registered",
                target_label=user.username,
                details={"role": user.role},
                request=request,
            )
        return render(
            request,
            "accounts/login_status.html",
            {"was_declined": False, "account_approved": user.is_approved},
        )
    return render(request, "accounts/register.html", {"form": form})


@login_required
@require_POST
def logout_view(request):
    logout(request)
    return redirect("accounts:login")


@administrator_required
def admin_dashboard(request):
    section = request.GET.get("section", "login-details")
    if section not in {"login-details", "requests", "activity"}:
        section = "login-details"

    role_filter = request.GET.get("role", "")
    valid_roles = {choice[0] for choice in User.Role.choices}
    if role_filter not in valid_roles:
        role_filter = ""

    context = {
        "section": section,
        "pending_request_count": LoginAccessRequest.objects.filter(
            status=LoginAccessRequest.Status.PENDING
        ).count(),
    }
    if section == "login-details":
        users = User.objects.annotate(
            latest_login_request_status=Subquery(
                LoginAccessRequest.objects.filter(user=OuterRef("pk"))
                .order_by("-requested_at", "-pk")
                .values("status")[:1]
            )
        ).order_by("role", "username")
        if role_filter:
            users = users.filter(role=role_filter)
        context.update(
            {
                "login_details": users,
                "role_filter": role_filter,
                "role_choices": User.Role.choices,
            }
        )
    elif section == "requests":
        context["pending_requests"] = LoginAccessRequest.objects.filter(
            status=LoginAccessRequest.Status.PENDING
        )
    else:
        context.update(
            {
                "audit_events": Paginator(
                    AuditEvent.objects.select_related("actor", "document"),
                    50,
                ).get_page(request.GET.get("page")),
                "audit_chain_valid": verify_audit_chain(),
            }
        )
    return render(request, "accounts/admin_dashboard.html", context)


@administrator_required
def admin_invitations(request):
    invitation_url = None
    if request.method == "POST":
        token, invitation = create_admin_invitation(request.user)
        invitation_url = request.build_absolute_uri(
            f"{reverse('accounts:register')}?invite={token}"
        )
        record_event(
            actor=request.user,
            action="admin_invitation_created",
            target_label="Administrator invitation",
            details={"invitation_id": invitation.pk},
            request=request,
        )
    return render(
        request,
        "accounts/admin_invitations.html",
        {"invitation_url": invitation_url},
    )


@administrator_required
def storage_health(request):
    status = check_private_storage()
    return render(
        request,
        "accounts/storage_health.html",
        {"storage_status": status},
        status=200 if status["healthy"] else 503,
    )


@administrator_required
def user_list(request):
    users = User.objects.order_by("role", "username")
    return render(request, "accounts/user_list.html", {"users": users})


@administrator_required
def user_create(request):
    form = UserCreateForm(
        request.POST or None,
        allow_admin=request.user.is_superuser,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
            if user.role != User.Role.ADMIN:
                LoginAccessRequest.objects.create(
                    user=user,
                    username_snapshot=user.username,
                    name_snapshot=user.display_name,
                )
            record_event(
                actor=request.user,
                action="account_created",
                target_label=user.username,
                details={"role": user.role},
                request=request,
            )
        messages.success(request, f"Created the {user.get_role_display().lower()} account.")
        return redirect("accounts:user_list")
    return render(request, "accounts/user_form.html", {"form": form})


@administrator_required
@require_POST
def user_delete(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    if user.pk == request.user.pk or user.is_superuser:
        return HttpResponseForbidden("You cannot delete this administrator account.")
    if user.role == User.Role.ADMIN and not request.user.is_superuser:
        return HttpResponseForbidden("Only a superuser can delete another administrator.")

    owned_documents = list(user.owned_documents.all())
    shared_documents = DocumentGrant.objects.filter(user=user).exclude(
        document__owner_id=user.pk
    ).select_related("document")
    files_to_delete = []
    files_to_delete.extend(
        (change_request.submitted_file.storage, change_request.submitted_file.name)
        for change_request in DocumentChangeRequest.objects.filter(
            Q(viewer=user) | Q(document__owner=user)
        )
        if change_request.submitted_file
    )
    with transaction.atomic():
        for grant in shared_documents:
            record_event(
                actor=request.user,
                action="document_access_revoked",
                target_label=grant.document.title,
                document=grant.document,
                details={
                    "recipient": user.username,
                    "reason": "account_deleted",
                },
                request=request,
            )
        for document in owned_documents:
            record_event(
                actor=request.user,
                action="document_deleted",
                target_label=document.title,
                document=document,
                details={"reason": "owner_account_deleted"},
                request=request,
            )
            files_to_delete.append((document.file.storage, document.file.name))
        record_event(
            actor=request.user,
            action="account_deleted",
            target_label=user.username,
            details={"role": user.role},
            request=request,
        )
        user.delete()
    for storage, file_name in files_to_delete:
        storage.delete(file_name)
    messages.success(request, "The account was deleted.")
    return redirect("accounts:user_list")


@administrator_required
def request_detail(request, request_id):
    access_request = get_object_or_404(
        LoginAccessRequest.objects.select_related("user"),
        pk=request_id,
    )
    return render(
        request,
        "accounts/request_detail.html",
        {"access_request": access_request},
    )


@administrator_required
@require_POST
def review_request(request, request_id):
    access_request = get_object_or_404(LoginAccessRequest, pk=request_id)
    decision = request.POST.get("decision")
    if decision not in {"approve", "decline"}:
        raise PermissionDenied("Invalid approval decision.")
    approved = decision == "approve"
    changed = review_login_request(access_request, request.user, approved)
    if changed:
        record_event(
            actor=request.user,
            action="login_request_approved" if approved else "login_request_declined",
            target_label=access_request.username_snapshot,
            details={"request_id": access_request.pk},
            request=request,
        )
        messages.success(
            request,
            "Login access approved." if approved else "Login access declined.",
        )
    else:
        messages.info(request, "This request was already reviewed.")
    return redirect("accounts:admin_dashboard")
