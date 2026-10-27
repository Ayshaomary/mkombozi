from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['kind', 'business', 'audience', 'created_at', 'read_at']
    list_filter = ['kind', 'audience']
    search_fields = ['business__name']
    readonly_fields = ['data', 'dedupe_key', 'created_at']
