"""Send email through Brevo's API (https://brevo.com).

An HTTP API rather than SMTP, because Render's free servers block the SMTP ports (25, 465, 587).
Without BREVO_API_KEY and EMAIL_FROM, email is switched off and features fall back to SMS.
"""

import json
from urllib import error, request

from django.conf import settings

TIMEOUT = 20


class EmailError(Exception):
    """The email could not be sent."""


def is_enabled():
    return bool(settings.BREVO_API_KEY and settings.EMAIL_FROM)


def send_email(to, subject, text):
    """Send one plain-text email."""
    req = request.Request(
        settings.BREVO_EMAIL_URL,
        data=json.dumps({
            'sender': {'name': settings.EMAIL_FROM_NAME, 'email': settings.EMAIL_FROM},
            'to': [{'email': to}],
            'subject': subject,
            'textContent': text,
        }).encode(),
        headers={
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'SAVIOR/1.0',
            'api-key': settings.BREVO_API_KEY,
        },
        method='POST',
    )
    try:
        with request.urlopen(req, timeout=TIMEOUT):
            pass
    except error.HTTPError as exc:
        raise EmailError(_error_message(exc)) from exc
    except (error.URLError, TimeoutError) as exc:
        raise EmailError(f'Could not reach Brevo: {exc}') from exc


def _error_message(exc):
    try:
        return json.load(exc).get('message') or f'Brevo error {exc.code}'
    except (ValueError, AttributeError):
        return f'Brevo error {exc.code}'
