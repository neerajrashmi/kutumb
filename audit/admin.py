import json
from django.contrib import admin
from django.utils.html import format_html
from .models import AuditRecord


@admin.register(AuditRecord)
class AuditRecordAdmin(admin.ModelAdmin):
    list_display = ('audit_id', 'audit_action', 'table_name', 'record_id', 'acting_user_id', 'audit_timestamp')
    list_filter = ('audit_action', 'table_name', 'audit_timestamp')
    search_fields = ('record_id', 'acting_user_id', 'table_name')
    readonly_fields = ('audit_id', 'table_name', 'record_id', 'audit_action', 'audit_timestamp', 'acting_user_id', 'pretty_snapshot')
    ordering = ('-audit_timestamp',)

    def pretty_snapshot(self, instance):
        """Displays readable formatted JSON in the admin inspection panel."""
        formatted_json = json.dumps(instance.row_snapshot, indent=2, default=str)
        return format_html('<pre style="background: #2b2b2b; color: #f8f8f2; padding: 12px; border-radius: 4px;">{}</pre>', formatted_json)

    pretty_snapshot.short_description = "Row Snapshot JSON"

    def has_add_permission(self, request):
        return False  # Audit records are immutable; cannot be manually created

    def has_change_permission(self, request, obj=None):
        return False  # Audit records cannot be modified

    def has_delete_permission(self, request, obj=None):
        return False  # Audit history cannot be deleted

    