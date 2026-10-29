"""Write an ActivityLog line for every change made through the API, and for every login attempt.

Reading data (GET) is not logged, only actions: adding, changing and deleting records, logging in,
and password changes. A problem while logging never stops the user's request.
"""

import json
import logging
import re

from accounts.models import User
from accounts.utils import normalize_phone

from .models import ActivityLog
from .services import record

logger = logging.getLogger(__name__)

Action = ActivityLog.Action

WRITE_METHODS = {'POST', 'PUT', 'PATCH', 'DELETE'}

# Too frequent or not done by a person, so not worth a line each.
# The admin dashboard (/api/admin/) writes its own, more detailed lines.
SKIP_PATHS = (
    '/api/auth/refresh/', '/api/notifications/', '/api/subscription/sonicpesa/webhook/',
    '/api/subscription/clickpesa/webhook/', '/api/admin/',
)

# Paths whose request has the phone number of a user who isn't logged in yet
PHONE_PATHS = ('/api/auth/login/', '/api/auth/password-reset/', '/api/auth/password-reset/confirm/')

NAMED_PATHS = {
    '/api/auth/login/': (Action.LOGIN, 'Logged in'),
    '/api/auth/register/': (Action.CREATE, 'Created an account and business'),
    '/api/auth/change-password/': (Action.PASSWORD, 'Changed password'),
    '/api/auth/password-reset/': (Action.PASSWORD, 'Asked for a password reset code'),
    '/api/auth/password-reset/confirm/': (Action.PASSWORD, 'Reset password with an SMS code'),
    '/api/auth/me/': (Action.UPDATE, 'Changed own profile'),
    '/api/auth/me/photo/': (Action.UPDATE, 'Changed profile photo'),
    '/api/business/': (Action.UPDATE, 'Changed business details'),
    '/api/business/logo/': (Action.UPDATE, 'Changed business logo'),
    '/api/subscription/payments/': (Action.CREATE, 'Started a subscription payment'),
}

# e.g. /api/products/, /api/products/12/, /api/products/12/adjust-stock/
RECORD_PATH = re.compile(r'^/api/(?P<resource>[a-z-]+)/(?:(?P<pk>\d+)/)?(?:(?P<extra>[a-z-]+)/)?$')

RESOURCE_NAMES = {
    'sales': 'sale',
    'products': 'product',
    'categories': 'category',
    'expenses': 'expense',
    'recurring-expenses': 'recurring expense',
    'stock-movements': 'stock movement',
    'staff': 'staff member',
    'recipes': 'recipe',
    'production': 'production batch',
}


class ActivityLogMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method not in WRITE_METHODS or not request.path.startswith('/api/') or request.path.startswith(SKIP_PATHS):
            return self.get_response(request)

        # Read the phone before the view does; the body can only be read here or by the view, not after both
        phone = _phone_from_body(request) if request.path in PHONE_PATHS else None
        response = self.get_response(request)
        try:
            _log(request, response, phone)
        except Exception:
            logger.exception('Could not write activity log for %s %s', request.method, request.path)
        return response


def _log(request, response, phone):
    status = response.status_code
    failed_login = request.path == '/api/auth/login/' and status == 401
    if not (200 <= status < 300 or failed_login):
        return

    data = getattr(response, 'data', None)
    data = data if isinstance(data, dict) else {}
    action, summary = _describe(request, data)
    if failed_login:
        action, summary = Action.LOGIN_FAILED, f'Failed login for {phone or "unknown number"}'

    record(request, _acting_user(request, data, phone), action, summary)


def _describe(request, data):
    if request.path in NAMED_PATHS:
        return NAMED_PATHS[request.path]

    match = RECORD_PATH.match(request.path)
    resource = match['resource'] if match else ''
    name = RESOURCE_NAMES.get(resource, resource.replace('-', ' ') or request.path)
    label = _label(data) or (f'#{match["pk"]}' if match and match['pk'] else '')
    target = f'{name} {label}'.strip()

    if match and match['extra']:
        return Action.OTHER, f'{match["extra"].replace("-", " ").capitalize()}: {target}'
    if request.method == 'POST':
        return Action.CREATE, f'Added {target}'
    if request.method == 'DELETE':
        return Action.DELETE, f'Deleted {target}'
    return Action.UPDATE, f'Changed {target}'


def _label(data):
    """A short name for the record, e.g. 'R-0012 (TZS 15,000)' or 'Sugar 1kg'."""
    name = (
        data.get('receipt_number') or data.get('batch_number') or data.get('name') or data.get('product_name')
        or data.get('description') or data.get('first_name') or ''
    )
    amount = data.get('total_amount') or data.get('amount') or data.get('total_cost')
    if amount not in (None, ''):
        try:
            name = f'{name} (TZS {float(amount):,.0f})'.strip()
        except (TypeError, ValueError):
            pass
    return str(name)


def _acting_user(request, data, phone):
    user = getattr(request, 'user', None)
    if user is not None and user.is_authenticated:
        return user
    # Login and register answer with the user who just got in
    user_id = (data.get('user') or {}).get('id') if isinstance(data.get('user'), dict) else None
    if user_id:
        return User.objects.filter(pk=user_id).first()
    if phone:
        return User.objects.filter(phone=normalize_phone(phone)).first()
    return None


def _phone_from_body(request):
    try:
        return str(json.loads(request.body or b'{}').get('phone') or '')[:20] or None
    except (ValueError, AttributeError):
        return None
