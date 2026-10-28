"""Production: turning raw materials into products for sale."""

from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.models import Business
from inventory.models import Product, StockMovement
from inventory.services import change_stock

from .models import ProductionRun, ProductionRunItem

CENTS = Decimal('0.01')


def next_batch_number(business):
    last = (
        ProductionRun.objects.filter(business=business).order_by('-id').values_list('batch_number', flat=True).first()
    )
    number = int(last[1:]) + 1 if last else 1
    return f'P{number:05d}'


@transaction.atomic
def record_production(business, user, product, quantity, items, extra_cost=Decimal(0), note='', produced_at=None):
    """Save a batch: take the materials out of stock and put the finished products in.

    `items` is a list of {'material': Product, 'quantity': Decimal}. The finished product's buying
    price becomes the average of the stock it already had and this batch, so profit on later sales
    is right. Either everything is saved or nothing is.
    """
    # Lock the business row so two batches saved at the same time get different numbers
    Business.objects.select_for_update().get(pk=business.pk)

    if any(item['material'].pk == product.pk for item in items):
        raise ValidationError({'items': 'A product cannot be made from itself.'})
    # If the same material appears twice, check stock for the combined quantity
    needed = defaultdict(Decimal)
    for item in items:
        needed[item['material'].pk] += item['quantity']
    for item in items:
        material = item['material']
        if needed[material.pk] > material.stock_quantity:
            raise ValidationError({
                'items': f'Not enough "{material.name}" in stock. Available: {material.stock_quantity}. '
                'Record the purchase of the material first.'
            })

    run = ProductionRun.objects.create(
        business=business,
        batch_number=next_batch_number(business),
        product=product,
        product_name=product.name,
        quantity=quantity,
        extra_cost=extra_cost,
        note=note,
        produced_at=min(produced_at or timezone.now(), timezone.now()),
        created_by=user,
    )
    materials_cost = Decimal(0)
    for item in items:
        material = item['material']
        subtotal = (material.cost_price * item['quantity']).quantize(CENTS, ROUND_HALF_UP)
        ProductionRunItem.objects.create(
            run=run,
            material=material,
            material_name=material.name,
            quantity=item['quantity'],
            unit_cost=material.cost_price,
            subtotal=subtotal,
        )
        change_stock(
            material, -item['quantity'], StockMovement.Type.USED_IN_PRODUCTION, user, f'Production {run.batch_number}'
        )
        materials_cost += subtotal

    run.materials_cost = materials_cost
    run.total_cost = materials_cost + extra_cost
    run.unit_cost = (run.total_cost / quantity).quantize(CENTS, ROUND_HALF_UP)
    run.save(update_fields=['materials_cost', 'total_cost', 'unit_cost'])

    # The new buying price: what the stock already there cost, plus this batch, per item
    product = Product.objects.select_for_update().get(pk=product.pk)
    old_stock = max(product.stock_quantity, Decimal(0))
    product.cost_price = ((old_stock * product.cost_price + run.total_cost) / (old_stock + quantity)).quantize(
        CENTS, ROUND_HALF_UP
    )
    product.save(update_fields=['cost_price', 'updated_at'])
    change_stock(product, quantity, StockMovement.Type.PRODUCED, user, f'Production {run.batch_number}')
    return run


@transaction.atomic
def cancel_production(run, user):
    """Undo a batch entered by mistake: the products leave stock and the materials come back.

    Not possible once the products of this batch have been sold. The buying price is left as it is.
    """
    note = f'Production {run.batch_number} cancelled'
    if run.product:
        product = Product.objects.select_for_update().get(pk=run.product.pk)
        if product.stock_quantity < run.quantity:
            raise ValidationError(
                f'Only {product.stock_quantity} "{product.name}" left in stock, so this batch of {run.quantity} '
                'cannot be cancelled. Some of it has already been sold.'
            )
        change_stock(product, -run.quantity, StockMovement.Type.PRODUCTION_CANCELLED, user, note)
    for item in run.items.select_related('material'):
        if item.material:
            change_stock(item.material, item.quantity, StockMovement.Type.PRODUCTION_CANCELLED, user, note)
    run.delete()
