"""Forgot password: send a 6-digit code by SMS, then let the user choose a new password with it."""

import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from notifications.sms import is_simulated, send_sms

from .models import PasswordResetCode, User

# A new code can be asked for after a minute, at most 5 times an hour
RESEND_AFTER = timedelta(seconds=60)
MAX_CODES_PER_HOUR = 5

MESSAGE = (
    'SAVIOR: {code} ni namba yako ya kubadilisha nenosiri (password reset code). '
    'Inaisha baada ya dakika 10. Usimpe mtu yeyote.'
)


class InvalidCode(Exception):
    """The code is wrong, used, expired, or was tried too many times."""


def request_code(phone):
    """Text a reset code to the account with this phone number, if there is one.

    It does nothing for unknown numbers, so this can't be used to find out who has an account.
    Raises notifications.sms.SMSError if the SMS could not be sent.
    In SMS simulation (a developer's computer, see notifications.sms.is_simulated) the code is
    returned instead, so the app can show it on screen; otherwise this returns None.
    """
    user = User.objects.filter(phone=phone, is_active=True).first()
    if user is None:
        return
    now = timezone.now()
    recent = user.password_reset_codes.filter(created_at__gt=now - timedelta(hours=1))
    if recent.count() >= MAX_CODES_PER_HOUR or recent.filter(created_at__gt=now - RESEND_AFTER).exists():
        return

    code = f'{secrets.randbelow(1_000_000):06d}'
    reset = PasswordResetCode.objects.create(user=user, code_hash=make_password(code))
    if is_simulated():
        print(f'\n[SMS simulation for {user.phone}] {MESSAGE.format(code=code)}\n', flush=True)
        return code
    try:
        send_sms(user.phone, MESSAGE.format(code=code))
    except Exception:
        # The user never got this code, so don't let it count against their limit
        reset.delete()
        raise


def reset_password(phone, code, new_password):
    """Set a new password if the code is right. Raises InvalidCode otherwise."""
    reset = PasswordResetCode.objects.filter(
        user__phone=phone,
        user__is_active=True,
        used_at__isnull=True,
        created_at__gt=timezone.now() - PasswordResetCode.LIFETIME,
    ).select_related('user').first()
    if reset is None or reset.attempts >= PasswordResetCode.MAX_ATTEMPTS:
        raise InvalidCode()

    if not check_password(code, reset.code_hash):
        PasswordResetCode.objects.filter(pk=reset.pk).update(attempts=F('attempts') + 1)
        raise InvalidCode()

    with transaction.atomic():
        # Mark the code used only if nobody else used it a moment ago
        used = PasswordResetCode.objects.filter(pk=reset.pk, used_at__isnull=True).update(used_at=timezone.now())
        if not used:
            raise InvalidCode()
        user = reset.user
        user.set_password(new_password)
        user.save(update_fields=['password'])
        # Older codes can't be used any more either
        user.password_reset_codes.filter(used_at__isnull=True).update(used_at=timezone.now())
    return user
