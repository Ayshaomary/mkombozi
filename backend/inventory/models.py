from django.conf import settings
from django.db import models


class Category(models.Model):
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='categories')
    name = models.CharField(max_length=100)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(fields=['business', 'name'], name='unique_category_per_business'),
        ]

    def __str__(self):
        return self.name


class Product(models.Model):
    class Unit(models.TextChoices):
        PIECE = 'piece', 'Piece'
        KG = 'kg', 'Kilogram'
        LITRE = 'litre', 'Litre'
        METRE = 'metre', 'Metre'
        BOX = 'box', 'Box'
        PACKET = 'packet', 'Packet'
        DOZEN = 'dozen', 'Dozen'
        BAG = 'bag', 'Bag'

    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='products')
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='products'
    )
    name = models.CharField(max_length=150)
    sku = models.CharField('SKU / barcode', max_length=50, blank=True)
    unit = models.CharField(max_length=10, choices=Unit.choices, default=Unit.PIECE)
    cost_price = models.DecimalField('buying price', max_digits=12, decimal_places=2)
    selling_price = models.DecimalField(max_digits=12, decimal_places=2)
    # Decimal so that items sold by weight or volume (e.g. 1.5 kg) are supported
    stock_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    low_stock_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=5)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold


class StockMovement(models.Model):
    """A record of every change to a product's stock, so the owner can see its full history."""

    class Type(models.TextChoices):
        OPENING = 'opening', 'Opening stock'
        PURCHASE = 'purchase', 'Purchase (stock in)'
        SALE = 'sale', 'Sale'
        SALE_CANCELLED = 'sale_cancelled', 'Sale cancelled'
        RETURN = 'return', 'Customer return'
        ADJUSTMENT = 'adjustment', 'Adjustment (damaged, lost, counted)'

    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='stock_movements')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=Type.choices)
    # Positive adds stock, negative removes stock
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    stock_after = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'{self.product} {self.quantity:+} ({self.get_movement_type_display()})'
