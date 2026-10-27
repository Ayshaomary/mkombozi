import math
import uuid
from datetime import timedelta

from django.db import models, transaction
from django.utils import timezone

TRIAL_DAYS = 14


class Plan(models.Model):
    """A subscription option, e.g. 1 month for TZS 10,000."""

    code = models.SlugField(unique=True)
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=12, decimal_places=2)
    duration_days = models.PositiveIntegerField(default=30)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['sort_order', 'price']

    def __str__(self):
        return f'{self.name} (TZS {self.price:,.0f})'


class Subscription(models.Model):
    class Status(models.TextChoices):
        TRIAL = 'trial', 'Free trial'
        ACTIVE = 'active', 'Active'
        CANCELLED = 'cancelled', 'Cancelled'

    business = models.OneToOneField(
        'accounts.Business', on_delete=models.CASCADE, related_name='subscription'
    )
    plan = models.ForeignKey(Plan, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.TRIAL)
    current_period_end = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.business} - {self.get_status_display()}'

    @classmethod
    def start_trial(cls, business):
        return cls.objects.create(
            business=business,
            status=cls.Status.TRIAL,
            current_period_end=timezone.now() + timedelta(days=TRIAL_DAYS),
        )

    @property
    def is_valid(self):
        """True while the business may add and change records."""
        return self.status != self.Status.CANCELLED and self.current_period_end > timezone.now()

    @property
    def days_left(self):
        # Round up, so a new 14-day trial shows 14 days, not 13 days and 23 hours
        seconds = (self.current_period_end - timezone.now()).total_seconds()
        return max(math.ceil(seconds / 86400), 0)


# How each mobile-money network's numbers start (Tanzania). The pay form in the app has the same list.
NETWORK_PREFIXES = {
    'mpesa': ('074', '075', '076', '079'),
    'tigopesa': ('065', '067', '071', '077'),
    'airtelmoney': ('068', '069', '078'),
    'halopesa': ('061', '062'),
}


class SubscriptionPayment(models.Model):
    class Provider(models.TextChoices):
        MPESA = 'mpesa', 'M-Pesa'
        TIGOPESA = 'tigopesa', 'Mixx by Yas (Tigo Pesa)'
        AIRTELMONEY = 'airtelmoney', 'Airtel Money'
        HALOPESA = 'halopesa', 'HaloPesa'
        MANUAL = 'manual', 'Manual / Bank'

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    business = models.ForeignKey(
        'accounts.Business', on_delete=models.CASCADE, related_name='subscription_payments'
    )
    plan = models.ForeignKey(Plan, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    phone = models.CharField(max_length=20)
    provider = models.CharField(max_length=20, choices=Provider.choices)
    reference = models.CharField(max_length=40, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    # Filled when the payment goes through SonicPesa (mobile money Push USSD)
    gateway_order_id = models.CharField(max_length=60, blank=True, db_index=True)
    gateway_transid = models.CharField(max_length=60, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.reference} - {self.business} - {self.get_status_display()}'

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = 'MKB-' + uuid.uuid4().hex[:10].upper()
        super().save(*args, **kwargs)

    @transaction.atomic
    def mark_completed(self):
        """Confirm the payment and extend the business's subscription by the plan's duration.

        Safe to call more than once, even at the same moment (e.g. a webhook and a status check).
        """
        # Lock the row and read the real status, so two calls can't both add the days
        status = SubscriptionPayment.objects.select_for_update().values_list('status', flat=True).get(pk=self.pk)
        if status == self.Status.COMPLETED:
            self.status = status
            return
        now = timezone.now()
        self.status = self.Status.COMPLETED
        self.completed_at = now
        self.save(update_fields=['status', 'completed_at'])

        subscription, _ = Subscription.objects.select_for_update().get_or_create(
            business=self.business, defaults={'current_period_end': now}
        )
        # Paying early adds time on top of what is left; paying late starts from today
        start = max(subscription.current_period_end, now)
        subscription.current_period_end = start + timedelta(days=self.plan.duration_days)
        subscription.plan = self.plan
        subscription.status = Subscription.Status.ACTIVE
        subscription.save()

    def mark_failed(self, reason=''):
        """Mark a pending payment as failed. A completed payment is never changed back."""
        updated = SubscriptionPayment.objects.filter(pk=self.pk, status=self.Status.PENDING).update(
            status=self.Status.FAILED, failure_reason=reason[:255]
        )
        if updated:
            self.status = self.Status.FAILED
            self.failure_reason = reason[:255]
