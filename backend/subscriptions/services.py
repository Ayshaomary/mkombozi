"""Subscription payments through SonicPesa: send the Push USSD, then follow the payment until it ends."""

import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings

from . import sonicpesa
from .models import SubscriptionPayment

logger = logging.getLogger(__name__)


def uses_sonicpesa(payment):
    return sonicpesa.is_enabled() and payment.provider != SubscriptionPayment.Provider.MANUAL


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
    """Ask SonicPesa about a payment that is still pending. If SonicPesa can't be reached, it stays pending."""
    if payment.status != SubscriptionPayment.Status.PENDING or not payment.gateway_order_id:
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


def _to_decimal(value):
    try:
        return Decimal(str(value))
    except InvalidOperation:
        return Decimal(0)
