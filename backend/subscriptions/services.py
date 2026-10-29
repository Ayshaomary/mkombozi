"""Subscription payments through SonicPesa (Push USSD) and ClickPesa (control numbers).

Start the payment, then follow it until it ends.
"""

import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.core.cache import cache

from . import clickpesa, sonicpesa
from .models import SubscriptionPayment

logger = logging.getLogger(__name__)

# Ask ClickPesa about the same control number at most once a minute
CONTROL_NUMBER_CHECK_SECONDS = 60


def uses_sonicpesa(payment):
    return sonicpesa.is_enabled() and payment.provider not in (
        SubscriptionPayment.Provider.MANUAL, SubscriptionPayment.Provider.CONTROL_NUMBER
    )


def create_control_number(payment):
    """Ask ClickPesa for a control number for this payment. On failure the payment is marked failed."""
    try:
        payment.control_number = clickpesa.create_control_number(
            amount=int(payment.amount),
            description=f'SAVIOR {payment.plan.name} - {payment.business.name}'[:100],
        )
    except clickpesa.ClickPesaError as exc:
        logger.warning('ClickPesa control number failed for %s: %s', payment.reference, exc)
        payment.mark_failed(str(exc))
        raise
    payment.save(update_fields=['control_number'])


def apply_clickpesa_payment(payment, data):
    """Update a payment from one ClickPesa payment record, whether from a webhook or a status check.

    A failed attempt doesn't fail the payment: the control number still works, so the payer can try again.
    """
    if (data.get('status') or '').upper() not in clickpesa.SUCCESS_STATUSES:
        return
    amount = data.get('collectedAmount')
    if amount is not None and _to_decimal(amount) < payment.amount:
        logger.error('ClickPesa paid %s for %s, expected %s', amount, payment.reference, payment.amount)
        return
    payment.gateway_transid = data.get('paymentReference') or data.get('id') or payment.gateway_transid
    payment.provider = clickpesa.provider_from_channel(data.get('channel')) or payment.provider
    payment.save(update_fields=['gateway_transid', 'provider'])
    payment.mark_completed()


def send_push(payment, user):
    """Ask SonicPesa to send a Push USSD to the payer's phone. On failure the payment is marked failed."""
    try:
        order = sonicpesa.create_order(
            phone=payment.phone.lstrip('+'),
            amount=int(payment.amount),
            name=user.get_full_name() or payment.business.name,
            email=user.email or settings.SONICPESA_BUYER_EMAIL,
        )
        order_id = order.get('order_id')
        if not order_id:
            raise sonicpesa.SonicPesaError('SonicPesa did not return an order id.')
    except sonicpesa.SonicPesaError as exc:
        logger.warning('SonicPesa push failed for %s: %s', payment.reference, exc)
        payment.mark_failed(str(exc))
        raise
    payment.gateway_order_id = order_id
    payment.save(update_fields=['gateway_order_id'])


def apply_gateway_status(payment, status, transid=None, channel=None, amount=None):
    """Update a payment from a SonicPesa status, whether it came from a webhook or a status check."""
    status = (status or '').upper()
    if status in sonicpesa.SUCCESS_STATUSES:
        if amount is not None and _to_decimal(amount) < payment.amount:
            logger.error('SonicPesa paid %s for %s, expected %s', amount, payment.reference, payment.amount)
            return
        payment.gateway_transid = transid or payment.gateway_transid
        payment.provider = sonicpesa.provider_from_channel(channel) or payment.provider
        payment.save(update_fields=['gateway_transid', 'provider'])
        payment.mark_completed()
    elif status in sonicpesa.FAILED_STATUSES:
        payment.mark_failed(status.lower())


def refresh_payment(payment):
    """Ask SonicPesa or ClickPesa about a payment that is still pending. If they can't be reached, it stays pending."""
    if payment.status != SubscriptionPayment.Status.PENDING:
        return payment
    if payment.control_number:
        return _refresh_control_number(payment)
    if not payment.gateway_order_id:
        return payment
    if not sonicpesa.is_enabled():
        return payment
    try:
        data = sonicpesa.order_status(payment.gateway_order_id)
    except sonicpesa.SonicPesaError as exc:
        logger.warning('SonicPesa status check failed for %s: %s', payment.reference, exc)
        return payment
    apply_gateway_status(
        payment,
        data.get('payment_status'),
        transid=data.get('transid'),
        channel=data.get('channel'),
        amount=data.get('amount'),
    )
    payment.refresh_from_db()
    return payment


def _refresh_control_number(payment):
    if not clickpesa.is_enabled():
        return payment
    # The app checks every few seconds, but ClickPesa limits API calls; the webhook usually comes first anyway
    if not cache.add(f'clickpesa_check:{payment.pk}', True, CONTROL_NUMBER_CHECK_SECONDS):
        return payment
    try:
        records = clickpesa.payment_status(payment.control_number)
    except clickpesa.ClickPesaError as exc:
        logger.warning('ClickPesa status check failed for %s: %s', payment.reference, exc)
        return payment
    for record in records:
        if isinstance(record, dict):
            apply_clickpesa_payment(payment, record)
        if payment.status == SubscriptionPayment.Status.COMPLETED:
            break
    payment.refresh_from_db()
    return payment


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal(0)
