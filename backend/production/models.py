from django.conf import settings
from django.db import models
from django.utils import timezone


class Recipe(models.Model):
    """What goes into making a product.

    Example: one batch makes 50 loaves (output_quantity) from 10 kg flour, 1 kg sugar and 0.2 kg yeast.
    """

    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='recipes')
    product = models.OneToOneField('inventory.Product', on_delete=models.CASCADE, related_name='recipe')
    output_quantity = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    note = models.CharField(max_length=255, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['product__name']

    def __str__(self):
        return f'Recipe for {self.product}'


class RecipeItem(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE, related_name='items')
    material = models.ForeignKey('inventory.Product', on_delete=models.CASCADE, related_name='used_in_recipes')
    # How much of the material one batch uses
    quantity = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']


class ProductionRun(models.Model):
    """One batch made: materials went out of stock and finished products came in."""

    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='production_runs')
    batch_number = models.CharField(max_length=20)
    # Kept even if the product is deleted later, so old batches still make sense
    product = models.ForeignKey(
        'inventory.Product', on_delete=models.SET_NULL, null=True, related_name='production_runs'
    )
    product_name = models.CharField(max_length=150)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    materials_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    # Other costs of this batch that are not stock, e.g. charcoal, labour, packaging
    extra_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    note = models.CharField(max_length=255, blank=True)
    produced_at = models.DateTimeField(default=timezone.now)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-produced_at', '-id']
        constraints = [
            models.UniqueConstraint(fields=['business', 'batch_number'], name='unique_batch_per_business'),
        ]
        indexes = [models.Index(fields=['business', 'produced_at'])]

    def __str__(self):
        return f'{self.batch_number} - {self.quantity} {self.product_name}'


class ProductionRunItem(models.Model):
    run = models.ForeignKey(ProductionRun, on_delete=models.CASCADE, related_name='items')
    # Counted to put the materials a business uses most at the top of the list
    material = models.ForeignKey(
        'inventory.Product', on_delete=models.SET_NULL, null=True, related_name='production_uses'
    )
    material_name = models.CharField(max_length=150)
    quantity = models.DecimalField(max_digits=12, decimal_places=2)
    # Buying price of the material at the time, so the batch cost stays correct when prices change
    unit_cost = models.DecimalField(max_digits=12, decimal_places=2)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']
