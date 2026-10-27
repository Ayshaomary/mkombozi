from django.db import IntegrityError, transaction

from .models import Notification


def notify(business, kind, data=None, audience=Notification.Audience.ALL, dedupe_key=None):
    """Create a notification. With a dedupe_key, the same notification is only ever created once.

    This is the single place where alerts are made, so SMS or WhatsApp can be added here later.
    """
    if dedupe_key is None:
        return Notification.objects.create(business=business, kind=kind, data=data or {}, audience=audience)
    try:
        # The savepoint keeps an outer transaction usable if two requests race to create the same one
        with transaction.atomic():
            notification, _ = Notification.objects.get_or_create(
                business=business,
                dedupe_key=dedupe_key,
                defaults={'kind': kind, 'data': data or {}, 'audience': audience},
            )
            return notification
    except IntegrityError:
        return Notification.objects.get(business=business, dedupe_key=dedupe_key)


def notify_stock_drop(product, old_quantity, new_quantity):
    """Alert when stock crosses down to the warning level or to zero (once per crossing, not every sale)."""
    if new_quantity <= 0 < old_quantity:
        kind = Notification.Kind.OUT_OF_STOCK
    elif new_quantity <= product.low_stock_threshold < old_quantity:
        kind = Notification.Kind.LOW_STOCK
    else:
        return None
    return notify(
        product.business,
        kind,
        {'product_id': product.pk, 'name': product.name, 'stock': str(new_quantity), 'unit': product.unit},
    )
