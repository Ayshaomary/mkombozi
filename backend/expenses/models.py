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
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-id']
        indexes = [models.Index(fields=['business', 'date'])]

    def __str__(self):
        return f'{self.get_category_display()} - TZS {self.amount:,.0f} ({self.date})'
