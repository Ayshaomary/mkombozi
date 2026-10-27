from django.db import models
from django.db.models import Q


class Notification(models.Model):
    """A message for the business, shown under the bell icon.

    We store the kind and its data (not finished text), so the app can show it in Kiswahili or English.
    """

    class Kind(models.TextChoices):
        LOW_STOCK = 'low_stock', 'Low stock'
        OUT_OF_STOCK = 'out_of_stock', 'Out of stock'
        DAILY_SUMMARY = 'daily_summary', 'Daily summary'
        RECURRING_EXPENSE = 'recurring_expense', 'Recurring expense recorded'
        SUBSCRIPTION_ENDING = 'subscription_ending', 'Subscription ending soon'
        SUBSCRIPTION_EXPIRED = 'subscription_expired', 'Subscription ended'

    class Audience(models.TextChoices):
        ALL = 'all', 'Everyone'
        OWNER = 'owner', 'Owner only'

    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='notifications')
    kind = models.CharField(max_length=30, choices=Kind.choices)
    audience = models.CharField(max_length=10, choices=Audience.choices, default=Audience.ALL)
    data = models.JSONField(default=dict, blank=True)
    # Stops the same notification being created twice, e.g. 'daily_summary:2026-10-26'
    dedupe_key = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['business', 'dedupe_key'],
                condition=Q(dedupe_key__isnull=False),
                name='unique_notification_key_per_business',
            ),
        ]
        indexes = [models.Index(fields=['business', 'read_at'])]

    def __str__(self):
        return f'{self.business} - {self.get_kind_display()}'
