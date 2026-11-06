from django.contrib import admin

from documents.models import AuditEvent, Document, DocumentGrant


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor", "action", "target_label", "event_hash")
    list_filter = ("action", "created_at")
    search_fields = ("target_label", "actor__username")
    readonly_fields = (
        "actor",
        "document",
        "action",
        "target_label",
        "details",
        "actor_reference",
        "document_reference",
        "created_at",
        "previous_hash",
        "event_hash",
    )

    def has_add_permission(self, _request):
        return False

    def has_change_permission(self, _request, _obj=None):
        return False

    def has_delete_permission(self, _request, _obj=None):
        return False


admin.site.register(Document)
admin.site.register(DocumentGrant)
