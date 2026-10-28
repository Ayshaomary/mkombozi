"""Send SMS through Beem Africa (https://beem.africa).

Without BEEM_API_KEY, messages are printed in the server's terminal instead, so features that send
SMS (like password reset) can be tried on a computer without paying for SMS.
"""

import base64
import json
import logging
from urllib import error, request

from django.conf import settings

logger = logging.getLogger(__name__)

TIMEOUT = 20


class SMSError(Exception):
    """The SMS could not be sent."""


def is_enabled():
    return bool(settings.BEEM_API_KEY and settings.BEEM_SECRET_KEY)


def is_simulated():
    """True on a developer's computer without SMS keys: messages are shown instead of sent.

    Never true on the live site (DEBUG is off there), because showing a reset code in the browser
    would let anyone take over any account.
    """
    return settings.DEBUG and not is_enabled()


def send_sms(phone, message):
    """Send one SMS. `phone` may be '+255712345678' or '255712345678'."""
    if not is_enabled():
        if not settings.DEBUG:
            raise SMSError('SMS is not set up. Add BEEM_API_KEY and BEEM_SECRET_KEY.')
        print(f'\n[SMS to {phone}] {message}\n', flush=True)
        return

    credentials = base64.b64encode(f'{settings.BEEM_API_KEY}:{settings.BEEM_SECRET_KEY}'.encode()).decode()
    req = request.Request(
        settings.BEEM_SMS_URL,
        data=json.dumps({
            'source_addr': settings.BEEM_SENDER_ID,
            'schedule_time': '',
            'encoding': 0,
            'message': message,
            'recipients': [{'recipient_id': 1, 'dest_addr': phone.lstrip('+')}],
        }).encode(),
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'SAVIOR/1.0',
            'Authorization': f'Basic {credentials}',
        },
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=TIMEOUT) as response:
            body = json.load(response)
    except error.HTTPError as exc:
        raise SMSError(_error_message(exc)) from exc
    except (error.URLError, TimeoutError, ValueError) as exc:
        raise SMSError(f'Could not reach Beem: {exc}') from exc
    # Beem answers {"successful": true, "code": 100, "message": "Message Submitted Successfully", ...}
    if not isinstance(body, dict) or not (body.get('successful') or body.get('code') == 100):
        message = body.get('message') if isinstance(body, dict) else None
        raise SMSError(message or 'Unexpected response from Beem.')


def _error_message(exc):
    try:
        return json.load(exc).get('message') or f'Beem error {exc.code}'
    except (ValueError, AttributeError):
        return f'Beem error {exc.code}'
