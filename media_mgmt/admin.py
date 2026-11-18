from django.contrib import admin
from .models import OccasionDetail, PhotoDetail, PhotoIndividualTag

class AuditedModelAdmin(admin.ModelAdmin):
    """Guarantees created_by and modified_by are populated in admin & popups."""
    readonly_fields = ('created_by', 'created_on', 'modified_by', 'modified_on')

    def save_model(self, request, obj, form, change):
        user_id = str(request.user.pk) if request.user.is_authenticated else 'SYSTEM'
        if not change or not obj.created_by:
            obj.created_by = user_id
        obj.modified_by = user_id
        super().save_model(request, obj, form, change)
        
@admin.register(OccasionDetail)
class OccasionDetailAdmin(admin.ModelAdmin):
    list_display = ('occasion_id', 'occasion_name', 'date', 'location')
    search_fields = ('occasion_name',)


class PhotoIndividualTagInline(admin.TabularInline):
    model = PhotoIndividualTag
    extra = 0


@admin.register(PhotoDetail)
class PhotoDetailAdmin(admin.ModelAdmin):
    list_display = (
        'photo_id', 'individual', 'marriage', 'occasion',
        'active_flag', 'file_size_bytes', 'created_on'
    )
    list_filter = ('active_flag', 'mime_type')
    search_fields = ('photo_id', 'caption', 'owner_uploader_id')
    inlines = [PhotoIndividualTagInline]


@admin.register(PhotoIndividualTag)
class PhotoIndividualTagAdmin(admin.ModelAdmin):
    list_display = (
        'photo_tag_id', 'photo', 'individual',
        'tagged_by_user_id', 'tag_status', 'approved_by_user_id'
    )
    list_filter = ('tag_status',)