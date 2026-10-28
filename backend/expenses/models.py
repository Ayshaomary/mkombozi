from calendar import monthrange
from datetime import date, timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class Expense(models.Model):
    """Money spent to run the business.

    Buying stock is NOT an expense here: its cost is counted when the goods are sold
    (cost of goods sold), so counting it again would reduce profit twice.
    """

    class Category(models.TextChoices):
        RENT = 'rent', 'Rent'
        SALARIES = 'salaries', 'Salaries & wages'
        TRANSPORT = 'transport', 'Transport'
        UTILITIES = 'utilities', 'Electricity & water'
        COMMUNICATION = 'communication', 'Phone & internet'
        TAXES = 'taxes', 'Taxes & licences'
        REPAIRS = 'repairs', 'Repairs & maintenance'
        MARKETING = 'marketing', 'Marketing'
        OTHER = 'other', 'Other'

    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='expenses')
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    date = models.DateField(default=timezone.localdate)
    # Set when the expense was recorded automatically by a recurring expense
    recurring = models.ForeignKey(
        'RecurringExpense', on_delete=models.SET_NULL, null=True, blank=True, related_name='expenses'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    # Made by the phone, so an expense sent twice (e.g. after the network dropped) is saved only once
    client_id = models.UUIDField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ['-date', '-id']
        indexes = [models.Index(fields=['business', 'date'])]
        constraints = [
            models.UniqueConstraint(fields=['business', 'client_id'], name='unique_expense_client_id_per_business'),
        ]

    def __str__(self):
        return f'{self.get_category_display()} - TZS {self.amount:,.0f} ({self.date})'


def nth_occurrence(start, frequency, n):
    """The date of the n-th repeat (n=0 is the start date).

    Months are counted from the start date, so the 31st becomes Feb 28 and then Mar 31 again.
    """
    if frequency == RecurringExpense.Frequency.DAILY:
        return start + timedelta(days=n)
    if frequency == RecurringExpense.Frequency.WEEKLY:
        return start + timedelta(weeks=n)
    years, month_index = divmod(start.month - 1 + n, 12)
    year, month = start.year + years, month_index + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


class RecurringExpense(models.Model):
    """An expense that repeats, e.g. rent of TZS 150,000 every month. Recorded automatically when due."""

    class Frequency(models.TextChoices):
        DAILY = 'daily', 'Every day'
        WEEKLY = 'weekly', 'Every week'
        MONTHLY = 'monthly', 'Every month'

    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='recurring_expenses')
    category = models.CharField(max_length=20, choices=Expense.Category.choices, default=Expense.Category.OTHER)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    description = models.CharField(max_length=255, blank=True)
    frequency = models.CharField(max_length=10, choices=Frequency.choices, default=Frequency.MONTHLY)
    start_date = models.DateField()
    # How many expenses have been recorded so far; the next one is due on next_date
    occurrences = models.PositiveIntegerField(default=0)
    next_date = models.DateField(db_index=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['next_date', 'id']

    def __str__(self):
        return f'{self.get_category_display()} - TZS {self.amount:,.0f} ({self.get_frequency_display()})'

    def save(self, *args, **kwargs):
        self.next_date = nth_occurrence(self.start_date, self.frequency, self.occurrences)
        super().save(*args, **kwargs)
