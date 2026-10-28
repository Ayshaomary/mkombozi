import ipaddress

from .models import ActivityLog


def record(request, user, action, summary):
    """Write one line in the activity log."""
    return ActivityLog.objects.create(
        user=user,
        business_id=getattr(user, 'business_id', None),
        action=action,
        summary=summary[:255],
        method=request.method,
        path=request.path[:255],
        ip_address=client_ip(request),
    )


def client_ip(request):
    # On Render, the visitor's address is the first one in X-Forwarded-For
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    ip = forwarded.split(',')[0].strip() if forwarded else request.META.get('REMOTE_ADDR', '')
    try:
        return str(ipaddress.ip_address(ip))
    except ValueError:
        return None
