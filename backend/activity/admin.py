from django.contrib import admin

from .models import ActivityLog


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    """What every user did, newest first. Read-only, so the history can't be changed."""

    list_display = ['created_at', 'user', 'business', 'action', 'summary', 'ip_address']
    list_filter = ['action', 'created_at', 'business']
    search_fields = ['summary', 'user__phone', 'user__first_name', 'user__last_name', 'business__name', 'ip_address']
    date_hierarchy = 'created_at'
    list_select_related = ['user', 'business']
    list_per_page = 100

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
