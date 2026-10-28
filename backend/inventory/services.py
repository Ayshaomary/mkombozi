from django.db import transaction
from rest_framework.exceptions import ValidationError

from notifications.services import notify_stock_drop

from .models import Product, StockMovement


@transaction.atomic
def change_stock(product, quantity, movement_type, user=None, note='', allow_negative=False):
    """Add (positive quantity) or remove (negative quantity) stock and record the movement.

    The product row is locked while we update it, so two cashiers selling the same item at
    the same moment cannot both sell the last one. `allow_negative` is for sales made offline:
    the money was already received, so the sale is kept and the owner is asked to check stock.
    """
    product = Product.objects.select_for_update().get(pk=product.pk)
    old_quantity = product.stock_quantity
    new_quantity = old_quantity + quantity
    if new_quantity < 0 and not allow_negative:
        raise ValidationError(
            {'quantity': f'Not enough stock for "{product.name}". Available: {product.stock_quantity}.'}
        )
    product.stock_quantity = new_quantity
    product.save(update_fields=['stock_quantity', 'updated_at'])
    StockMovement.objects.create(
        business_id=product.business_id,
        product=product,
        movement_type=movement_type,
        quantity=quantity,
        stock_after=new_quantity,
        note=note,
        created_by=user,
    )
    notify_stock_drop(product, old_quantity, new_quantity)
    return product
