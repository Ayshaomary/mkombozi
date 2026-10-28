from collections import defaultdict

from django.db import transaction
from rest_framework.exceptions import ValidationError

from accounts.models import Business
from inventory.models import StockMovement
from inventory.services import change_stock

from .models import Sale, SaleItem


def next_receipt_number(business):
    last = Sale.objects.filter(business=business).order_by('-id').values_list('receipt_number', flat=True).first()
    number = int(last[1:]) + 1 if last else 1
    return f'R{number:05d}'


@transaction.atomic
def create_sale(business, user, items, **sale_fields):
    """Save a sale and reduce stock for every item. Either everything is saved or nothing is.

    `items` is a list of {'product': Product, 'quantity': Decimal, 'unit_price': Decimal or None}.
    A sale recorded offline is kept even without enough stock: the money was already received,
    and the product's stock goes below zero so the owner sees it needs checking.
    """
    offline = sale_fields.get('recorded_offline', False)
    # Lock the business row so two sales saved at the same time get different receipt numbers
    Business.objects.select_for_update().get(pk=business.pk)

    # If the same product appears twice, check stock for the combined quantity
    totals = defaultdict(int)
    for item in items:
        totals[item['product'].pk] += item['quantity']
    for item in items:
        product = item['product']
        if totals[product.pk] > product.stock_quantity and not offline:
            raise ValidationError(
                {'items': f'Not enough stock for "{product.name}". Available: {product.stock_quantity}.'}
            )

    sale = Sale.objects.create(
        business=business, created_by=user, receipt_number=next_receipt_number(business), **sale_fields
    )
    items_total = 0
    total_cost = 0
    for item in items:
        product = item['product']
        unit_price = item.get('unit_price')
        if unit_price is None:
            unit_price = product.selling_price
        subtotal = unit_price * item['quantity']
        SaleItem.objects.create(
            sale=sale,
            product=product,
            product_name=product.name,
            quantity=item['quantity'],
            unit_price=unit_price,
            unit_cost=product.cost_price,
            subtotal=subtotal,
        )
        change_stock(
            product, -item['quantity'], StockMovement.Type.SALE, user, f'Sale {sale.receipt_number}',
            allow_negative=offline,
        )
        items_total += subtotal
        total_cost += product.cost_price * item['quantity']

    if sale.discount > items_total:
        raise ValidationError({'discount': 'Discount cannot be more than the sale total.'})
    sale.total_amount = items_total - sale.discount
    sale.total_cost = total_cost
    sale.save(update_fields=['total_amount', 'total_cost'])
    return sale


@transaction.atomic
def cancel_sale(sale, user):
    """Delete a sale and put its items back into stock."""
    for item in sale.items.select_related('product'):
        if item.product:
            change_stock(
                item.product, item.quantity, StockMovement.Type.SALE_CANCELLED, user,
                f'Sale {sale.receipt_number} cancelled',
            )
    sale.delete()
