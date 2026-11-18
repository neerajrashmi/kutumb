from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.serializers import serialize
import json

from common.middleware import get_current_user_id
from audit.models import AuditRecord

# Import all audited domain models
from genealogy.models import IndividualDetail, MarriageDetail
from accounts.models import UserDetail, UserAccess, UserAccessScope
from common.models import DateDetail, LocationDetail
from contacts.models import IndividualAddress, IndividualPhone, IndividualEmail
from media_mgmt.models import PhotoDetail, OccasionDetail, PhotoIndividualTag

AUDITED_MODELS = (
    IndividualDetail,
    MarriageDetail,
    UserDetail,
    UserAccess,
    UserAccessScope,
    DateDetail,
    LocationDetail,
    PhotoDetail,
    OccasionDetail,
    PhotoIndividualTag,
    IndividualAddress,
    IndividualPhone,
    IndividualEmail,
)


def get_model_snapshot(instance):
    """Serializes the model instance fields to a clean JSON dict."""
    serialized_data = serialize('json', [instance])
    data_list = json.loads(serialized_data)
    if data_list:
        fields = data_list[0]['fields']
        fields['pk'] = data_list[0]['pk']
        return fields
    return {}


@receiver(post_save)
def audit_post_save(sender, instance, created, **kwargs):
    if sender in AUDITED_MODELS:
        acting_user = get_current_user_id()
        action = 'INSERT' if created else 'UPDATE'
        table_name = instance._meta.db_table
        record_id = str(instance.pk)
        snapshot = get_model_snapshot(instance)

        AuditRecord.objects.create(
            table_name=table_name,
            record_id=record_id,
            audit_action=action,
            acting_user_id=acting_user or getattr(instance, 'modified_by', None) or 'SYSTEM',
            row_snapshot=snapshot
        )


@receiver(post_delete)
def audit_post_delete(sender, instance, **kwargs):
    if sender in AUDITED_MODELS:
        acting_user = get_current_user_id()
        table_name = instance._meta.db_table
        record_id = str(instance.pk)
        snapshot = get_model_snapshot(instance)

        AuditRecord.objects.create(
            table_name=table_name,
            record_id=record_id,
            audit_action='DELETE',
            acting_user_id=acting_user or getattr(instance, 'modified_by', None) or 'SYSTEM',
            row_snapshot=snapshot
        )