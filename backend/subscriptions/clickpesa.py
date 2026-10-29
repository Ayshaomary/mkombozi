"""Small client for the ClickPesa BillPay API (https://docs.clickpesa.com).

Only what subscriptions need: create a control number for a payment, check whether it was paid,
and check that a webhook really came from ClickPesa. The payer types the control number into
M-Pesa, Mixx by Yas, Airtel Money, HaloPesa or CRDB. Without CLICKPESA_CLIENT_ID and
CLICKPESA_API_KEY it is switched off, and the app doesn't offer control numbers.
"""

import hashlib
import hmac
import json
from urllib import error, request

from django.conf import settings
from django.core.cache import cache

TIMEOUT = 30
TOKEN_CACHE_KEY = 'clickpesa_token'
# A token works for 1 hour; get a new one a little before that
TOKEN_SECONDS = 55 * 60

# ClickPesa payment statuses, grouped by what they mean for us
SUCCESS_STATUSES = {'SUCCESS', 'SETTLED'}
FAILED_STATUSES = {'FAILED'}

# Words in ClickPesa's "channel" -> our SubscriptionPayment.Provider values
CHANNEL_PROVIDERS = {
    'MPESA': 'mpesa',
    'M-PESA': 'mpesa',
    'VODACOM': 'mpesa',
    'TIGO': 'tigopesa',
    'MIXX': 'tigopesa',
    'AIRTEL': 'airtelmoney',
    'HALO': 'halopesa',
}


class ClickPesaError(Exception):
    """ClickPesa could not be reached, or it refused the request."""


def is_enabled():
    return bool(settings.CLICKPESA_CLIENT_ID and settings.CLICKPESA_API_KEY)


def _call(method, path, payload=None, headers=None):
    req = request.Request(
        settings.CLICKPESA_BASE_URL.rstrip('/') + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'SAVIOR/1.0',
            **(headers or {}),
        },
        method=method,
    )
    try:
        with request.urlopen(req, timeout=TIMEOUT) as response:
            return json.load(response)
    except error.HTTPError as exc:
        if exc.code == 401:
            # The saved token may have expired early; the next call gets a new one
            cache.delete(TOKEN_CACHE_KEY)
        raise ClickPesaError(_error_message(exc)) from exc
    except (error.URLError, TimeoutError, ValueError) as exc:
        raise ClickPesaError(f'Could not reach ClickPesa: {exc}') from exc


def _error_message(exc):
    try:
        return json.load(exc).get('message') or f'ClickPesa error {exc.code}'
    except (ValueError, AttributeError):
        return f'ClickPesa error {exc.code}'


def _token():
    token = cache.get(TOKEN_CACHE_KEY)
    if token:
        return token
    body = _call('POST', '/third-parties/generate-token', headers={
        'client-id': settings.CLICKPESA_CLIENT_ID,
        'api-key': settings.CLICKPESA_API_KEY,
    })
    token = body.get('token') if isinstance(body, dict) else None
    if not token:
        raise ClickPesaError('ClickPesa did not return a token.')
    # The token already starts with "Bearer "
    cache.set(TOKEN_CACHE_KEY, token, TOKEN_SECONDS)
    return token


def _authorized(method, path, payload=None):
    return _call(method, path, payload, headers={'Authorization': _token()})


def create_control_number(amount, description):
    """Make a control number that accepts exactly `amount` TZS. Returns the number as a string."""
    body = _authorized('POST', '/third-parties/billpay/create-order-control-number', {
        'billDescription': description,
        'billAmount': amount,
        'billPaymentMode': 'EXACT',
    })
    number = body.get('billPayNumber') if isinstance(body, dict) else None
    if not number:
        raise ClickPesaError('ClickPesa did not return a control number.')
    return str(number)


def payment_status(control_number):
    """The payments made to a control number (a list, empty while nobody has paid)."""
    try:
        body = _authorized('GET', f'/third-parties/payments/{control_number}')
    except ClickPesaError as exc:
        # ClickPesa answers 404 until the first payment arrives
        if 'Invalid or missing payment' in str(exc):
            return []
        raise
    return body if isinstance(body, list) else []


def _sorted(value):
    if isinstance(value, dict):
        return {key: _sorted(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_sorted(item) for item in value]
    return value


def checksum(payload):
    """HMAC-SHA256 of the payload as compact JSON with keys sorted, made with our checksum key."""
    body = {k: v for k, v in payload.items() if k not in ('checksum', 'checksumMethod')}
    text = json.dumps(_sorted(body), separators=(',', ':'), ensure_ascii=False)
    return hmac.new(settings.CLICKPESA_CHECKSUM_KEY.encode(), text.encode(), hashlib.sha256).hexdigest()


def verify_checksum(payload):
    """True if the webhook carries a checksum made with our checksum key.

    The checksum may sit at the top of the webhook or inside its "data" part; it covers the part it sits in.
    """
    if not settings.CLICKPESA_CHECKSUM_KEY or not isinstance(payload, dict):
        return False
    signed = payload if 'checksum' in payload else payload.get('data')
    if not isinstance(signed, dict) or not isinstance(signed.get('checksum'), str):
        return False
    return hmac.compare_digest(checksum(signed), signed['checksum'].strip().lower())


def provider_from_channel(channel):
    channel = (channel or '').upper()
    return next((provider for word, provider in CHANNEL_PROVIDERS.items() if word in channel), None)
