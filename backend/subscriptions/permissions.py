from rest_framework.permissions import SAFE_METHODS, BasePermission


class HasActiveSubscription(BasePermission):
    """Viewing is always allowed; adding or changing records needs a trial or paid subscription."""

    message = 'Your subscription has ended. Please renew to keep adding records.'

    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        subscription = getattr(request.user.business, 'subscription', None)
        return bool(subscription and subscription.is_valid)
