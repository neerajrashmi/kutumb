from django.db import models
from django.utils import timezone


class AuditRecord(models.Model):
    """
    Physical Schema: aud_* shadow implementation.
    Preserves point-in-time snapshots, acting user, operation, and UTC timestamp.
    """
    ACTION_CHOICES = [
        ('INSERT', 'Insert'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('PURGE', 'Purge'),
    ]

    audit_id = models.BigAutoField(primary_key=True, db_column='Audit_Id')
    table_name = models.CharField(max_length=64, db_column='Table_Name', db_index=True)
    record_id = models.CharField(max_length=64, db_column='Record_Id', db_index=True)
    audit_action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_column='Audit_Action')
    audit_timestamp = models.DateTimeField(default=timezone.now, editable=False, db_column='Audit_Timestamp')
    acting_user_id = models.CharField(max_length=8, null=True, blank=True, db_column='Acting_User_Id', db_index=True)
    row_snapshot = models.JSONField(db_column='Row_Snapshot_JSON')

    class Meta:
        db_table = 'aud_System_Audit_Log'
        ordering = ['-audit_timestamp']
        indexes = [
            models.Index(fields=['record_id', 'audit_timestamp'], name='ix_aud_record_time'),
            models.Index(fields=['acting_user_id', 'audit_timestamp'], name='ix_aud_user_time'),
            models.Index(fields=['table_name', 'record_id'], name='ix_aud_table_rec'),
        ]

    def __str__(self):
        return f"[{self.audit_action}] {self.table_name}:{self.record_id} by {self.acting_user_id} at {self.audit_timestamp}"