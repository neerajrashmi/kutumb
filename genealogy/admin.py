from django.contrib import admin
from .models import IndividualDetail, MarriageDetail


@admin.register(IndividualDetail)
class IndividualDetailAdmin(admin.ModelAdmin):
    list_display = ('individual_id', 'first_name', 'middle_name', 'last_name', 'gender', 'birth_date', 'created_by', 'created_on', 'modified_by')
    search_fields = ('individual_id', 'first_name', 'last_name')
    readonly_fields = ('individual_id', 'created_by', 'created_on', 'modified_by', 'modified_on')
    # Enables popup search/creation modal for linked DateDetail and LocationDetail
    autocomplete_fields = [
        'birth_date', 
        'birth_location', 
        'death_date', 
        'death_location', 
        'parent_marriage'
    ]
    fieldsets = (
        ('System Identification', {
            'fields': ('individual_id',)
        }),
        ('Name & Demographic Information', {
            'fields': ('first_name', 'middle_name', 'last_name', 'gender')
        }),
        ('Birth Event', {
            'fields': ('birth_date', 'birth_location')
        }),
        ('Death Event', {
            'fields': ('death_date', 'death_location')
        }),
        ('Lineage / Parent Union', {
            'fields': ('parent_marriage',)
        }),
        ('Audit Metadata', {
            'classes': ('collapse',),
            'fields': ('created_by', 'created_on', 'modified_by', 'modified_on')
        }),
    )

@admin.register(MarriageDetail)
class MarriageDetailAdmin(admin.ModelAdmin):
    list_display = ('marriage_id', 'male_member', 'female_member', 'separation_reason', 'created_by', 'created_on')
    readonly_fields = ('marriage_id', 'created_by', 'created_on', 'modified_by', 'modified_on')
    search_fields = (
        'marriage_id',
        'male_member__first_name',
        'male_member__last_name',
        'male_member__individual_id',
        'female_member__first_name',
        'female_member__last_name',
        'female_member__individual_id',
    )
    
    readonly_fields = ('marriage_id', 'created_by', 'created_on', 'modified_by', 'modified_on')
    autocomplete_fields = [
        'male_member', 
        'female_member', 
        'marriage_date', 
        'marriage_location', 
        'separation_date'
    ]

    fieldsets = (
        ('System Identification', {
            'fields': ('marriage_id',)
        }),
        ('Participants', {
            'fields': ('male_member', 'female_member')
        }),
        ('Marriage Event', {
            'fields': ('marriage_date', 'marriage_location')
        }),
        ('Separation Event', {
            'fields': ('separation_date', 'separation_reason')
        }),
        ('Audit Metadata', {
            'classes': ('collapse',),
            'fields': ('created_by', 'created_on', 'modified_by', 'modified_on')
        }),
    )