from django.conf import settings
from django.db import models
from django.utils import timezone


class PaymentMethod(models.TextChoices):
    CASH = 'cash', 'Cash'
    MPESA = 'mpesa', 'M-Pesa'
    TIGOPESA = 'tigopesa', 'Mixx by Yas (Tigo Pesa)'
    AIRTELMONEY = 'airtelmoney', 'Airtel Money'
    HALOPESA = 'halopesa', 'HaloPesa'
    BANK = 'bank', 'Bank / Card'
    CREDIT = 'credit', 'Credit (deni)'


class Sale(models.Model):
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='sales')
    receipt_number = models.CharField(max_length=20)
    customer_name = models.CharField(max_length=150, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    payment_method = models.CharField(max_length=20, choices=PaymentMethod.choices, default=PaymentMethod.CASH)
    discount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # What the customer pays (items total minus discount)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # What the sold items cost the business to buy
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.CharField(max_length=255, blank=True)
    # When the sale happened (can be earlier than created_at if recorded later)
    sold_at = models.DateTimeField(default=timezone.now)
    # Made by the phone, so a sale sent twice (e.g. after the network dropped) is saved only once
    client_id = models.UUIDField(null=True, blank=True, editable=False)
    # Recorded without internet and sent later; stock may then have gone below zero
    recorded_offline = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-sold_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['business', 'receipt_number'], name='unique_receipt_per_business'),
            models.UniqueConstraint(fields=['business', 'client_id'], name='unique_sale_client_id_per_business'),
        ]
        indexes = [models.Index(fields=['business', 'sold_at'])]

    def __str__(self):
        return f'{self.receipt_number} - TZS {self.total_amount:,.0f}'

    @property
    def profit(self):
        return self.total_amount - self.total_cost


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name='items')
    # Kept even if the product is deleted later, so old receipts still make sense
    product = models.ForeignKey('inventory.Product', on_delete=models.SET_NULL, null=True, related_name='sale_items')
    product_name = models.CharField(max_length=150)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    # Buying price at the time of sale, so profit stays correct when prices change
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    def __str__(self):
        return f'{self.quantity} x {self.product_name}'
