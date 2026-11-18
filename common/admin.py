# apps/common/admin.py
from django.contrib import admin
from .models import DateDetail, LocationDetail, IdSequence


@admin.register(IdSequence)
class IdSequenceAdmin(admin.ModelAdmin):
    list_display = ('sequence_type', 'next_val')
    search_fields = ('sequence_type',)


@admin.register(DateDetail)
class DateDetailAdmin(admin.ModelAdmin):
    list_display = (
        'date_id',
        'precision',
        'original_text',
        'start_date',
        'end_date',
        'year_val',
        'created_on',
    )
    list_filter = ('precision', 'created_on')
    search_fields = ('original_text', 'date_id')
    readonly_fields = ('created_on', 'modified_on')


@admin.register(LocationDetail)
class LocationDetailAdmin(admin.ModelAdmin):
    list_display = (
        'location_id',
        'original_location',
        'google_formatted_address',
        'latitude',
        'longitude',
        'status',
        'created_on',
    )
    list_filter = ('status', 'created_on')
    search_fields = ('original_location', 'google_formatted_address', 'google_place_id')
    readonly_fields = ('created_on', 'modified_on')