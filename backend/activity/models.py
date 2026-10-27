from django.conf import settings
from django.db import models


class ActivityLog(models.Model):
    """One thing a user did in the app: logged in, recorded a sale, changed a product, ..."""

    class Action(models.TextChoices):
        CREATE = 'create', 'Added'
        UPDATE = 'update', 'Changed'
        DELETE = 'delete', 'Deleted'
        LOGIN = 'login', 'Logged in'
        LOGIN_FAILED = 'login_failed', 'Failed login'
        PASSWORD = 'password', 'Password'
        OTHER = 'other', 'Other'

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='activities'
    )
    business = models.ForeignKey(
        'accounts.Business', on_delete=models.SET_NULL, null=True, blank=True, related_name='activities'
    )
    action = models.CharField(max_length=20, choices=Action.choices)
    summary = models.CharField(max_length=255)
    method = models.CharField(max_length=10)
    path = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.created_at:%Y-%m-%d %H:%M} {self.user or "-"}: {self.summary}'
