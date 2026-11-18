from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import UserDetail, UserAccess, UserAccessScope


@admin.register(UserDetail)
class UserDetailAdmin(BaseUserAdmin):
    list_display = ('user_id', 'user_status', 'is_staff', 'is_superuser', 'created_on')
    list_filter = ('user_status', 'is_staff', 'is_superuser')
    search_fields = ('user_id__individual_id', 'user_id__first_name', 'user_id__last_name')
    ordering = ('user_id',)

    fieldsets = (
        (None, {'fields': ('user_id', 'password')}),
        ('Status & Provenance', {'fields': ('user_status', 'invited_by_user')}),
        ('Permissions', {'fields': ('is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Audit', {'fields': ('created_by', 'created_on', 'modified_by', 'modified_on')}),
    )
    readonly_fields = ('created_on', 'modified_on')

    # Exclude add_fieldsets standard username prompts
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('user_id', 'password', 'user_status', 'is_staff', 'is_superuser'),
        }),
    )


class UserAccessScopeInline(admin.TabularInline):
    model = UserAccessScope
    extra = 1


@admin.register(UserAccess)
class UserAccessAdmin(admin.ModelAdmin):
    list_display = ('access_id', 'host_user', 'granted_to_user', 'access_type', 'access_status', 'granted_on')
    list_filter = ('access_type', 'access_status')
    search_fields = ('host_user__user_id__individual_id', 'granted_to_user__user_id__individual_id')
    inlines = [UserAccessScopeInline]