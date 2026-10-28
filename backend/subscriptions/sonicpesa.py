"""Small client for the SonicPesa mobile-money API (https://sonicpesa.com).

Only what subscriptions need: send a Push USSD to the customer's phone, check an order's status,
and check that a webhook really came from SonicPesa. Without SONICPESA_API_KEY it is switched off,
and payments wait for an admin to confirm them instead.
"""

import hashlib
import hmac
import json
from urllib import error, request

from django.conf import settings

TIMEOUT = 30

# SonicPesa payment statuses, grouped by what they mean for us
SUCCESS_STATUSES = {'SUCCESS', 'COMPLETED'}
FAILED_STATUSES = {'CANCELLED', 'USERCANCELLED', 'REJECTED', 'FAILED'}

# Words in SonicPesa's "channel" (e.g. TIGOPESATZ) -> our SubscriptionPayment.Provider values
CHANNEL_PROVIDERS = {
    'MPESA': 'mpesa',
    'VODACOM': 'mpesa',
    'TIGO': 'tigopesa',
    'MIXX': 'tigopesa',
    'AIRTEL': 'airtelmoney',
    'HALO': 'halopesa',
}


class SonicPesaError(Exception):
    """SonicPesa could not be reached, or it refused the request."""


def is_enabled():
    return bool(settings.SONICPESA_API_KEY)


def _post(path, payload):
    req = request.Request(
        settings.SONICPESA_BASE_URL.rstrip('/') + path,
        data=json.dumps(payload).encode(),
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'SAVIOR/1.0',
            'X-API-KEY': settings.SONICPESA_API_KEY,
        },
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=TIMEOUT) as response:
            body = json.load(response)
    except error.HTTPError as exc:
        raise SonicPesaError(_error_message(exc)) from exc
    except (error.URLError, TimeoutError, ValueError) as exc:
        raise SonicPesaError(f'Could not reach SonicPesa: {exc}') from exc
    if not isinstance(body, dict) or body.get('status') != 'success':
        message = body.get('message') if isinstance(body, dict) else None
        raise SonicPesaError(message or 'Unexpected response from SonicPesa.')
    return body.get('data') or {}


def _error_message(exc):
    try:
        return json.load(exc).get('message') or f'SonicPesa error {exc.code}'
    except (ValueError, AttributeError):
        return f'SonicPesa error {exc.code}'


def create_order(phone, amount, name, email):
    """Start a payment: SonicPesa sends a Push USSD and the customer approves it with their PIN.

    `phone` is like 255712345678 (no plus sign). Returns the order data, including `order_id`.
    """
    return _post('/payment/create_order', {
        'buyer_email': email,
        'buyer_name': name,
        'buyer_phone': phone,
        'amount': amount,
        'currency': 'TZS',
    })


def order_status(order_id):
    """Current state of an order. `payment_status` is one of SUCCESS, PENDING, INPROGRESS, CANCELLED..."""
    return _post('/payment/order_status', {'order_id': order_id})


def verify_signature(raw_body, signature):
    """True if the webhook was signed with our API secret (HMAC-SHA256 of the raw body)."""
    secret = settings.SONICPESA_API_SECRET
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature.strip().lower())


def provider_from_channel(channel):
    channel = (channel or '').upper()
    return next((provider for word, provider in CHANNEL_PROVIDERS.items() if word in channel), None)
