from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from accounts.models import LoginAccessRequest, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        ("TrustVault access", {"fields": ("role", "is_approved")}),
    )
    add_fieldsets = DjangoUserAdmin.add_fieldsets + (
        ("TrustVault access", {"fields": ("role", "is_approved")}),
    )
    list_display = ("username", "email", "role", "is_approved", "is_active", "is_superuser")
    list_filter = ("role", "is_approved", "is_active", "is_superuser")


@admin.register(LoginAccessRequest)
class LoginAccessRequestAdmin(admin.ModelAdmin):
    list_display = ("username_snapshot", "name_snapshot", "status", "requested_at", "reviewed_by")
    readonly_fields = (
        "user",
        "username_snapshot",
        "name_snapshot",
        "status",
        "requested_at",
        "reviewed_at",
        "reviewed_by",
    )

    def has_add_permission(self, _request):
        return False

    def has_change_permission(self, _request, _obj=None):
        return False

    def has_delete_permission(self, _request, _obj=None):
        return False
