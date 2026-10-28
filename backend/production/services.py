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


def find_material(business, name):
    """A product of this business with this name (any capitals), if there is one."""
    return Product.objects.filter(business=business, name__iexact=name.strip()).first()


def create_material(business, name, unit, unit_cost):
    """A raw material typed by the user that the business didn't have yet."""
    return Product.objects.create(
        business=business,
        name=name.strip(),
        unit=unit or Product.Unit.PIECE,
        cost_price=unit_cost or 0,
        selling_price=0,
        stock_quantity=0,
        is_material=True,
    )


def resolve_items(business, items):
    """Turn each line into {'material': Product, 'quantity', 'new': bool}.

    A line has either a chosen material, or a typed name: an existing product with that name is
    used, otherwise a new raw material is made with the typed unit and price.
    """
    resolved = []
    created = {}  # the same new name typed on two lines is one material
    for item in items:
        key = (item.get('name') or '').strip().lower()
        material = item.get('material') or created.get(key) or find_material(business, item['name'])
        new = material is None or key in created
        if material is None:
            material = created[key] = create_material(business, item['name'], item.get('unit'), item.get('unit_cost'))
        resolved.append({'material': material, 'quantity': item['quantity'], 'new': new})
    return resolved


@transaction.atomic
def record_production(business, user, product, quantity, items, extra_cost=Decimal(0), note='', produced_at=None):
    """Save a batch: take the materials out of stock and put the finished products in.

    `items` is a list of {'material': Product, 'quantity': Decimal}, or {'name', 'unit', 'unit_cost',
    'quantity'} for a material typed by name (see resolve_items). A material the business didn't
    have yet counts as bought today and used straight away. The finished product's buying price
    becomes the average of the stock it already had and this batch, so profit on later sales is
    right. Either everything is saved or nothing is.
    """
    # Lock the business row so two batches saved at the same time get different numbers
    Business.objects.select_for_update().get(pk=business.pk)

    items = resolve_items(business, items)
    if any(item['material'].pk == product.pk for item in items):
        raise ValidationError({'items': 'A product cannot be made from itself.'})
    # If the same material appears twice, check stock for the combined quantity
    needed = defaultdict(Decimal)
    for item in items:
        needed[item['material'].pk] += item['quantity']
    for item in items:
        material = item['material']
        if not item['new'] and needed[material.pk] > material.stock_quantity:
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
        if item['new']:
            change_stock(
                material, item['quantity'], StockMovement.Type.PURCHASE, user, f'Bought for production {run.batch_number}'
            )
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
