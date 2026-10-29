"""Forgot password: send a 6-digit code by email or SMS, then let the user choose a new password with it."""

import logging
import secrets
from datetime import timedelta

from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from notifications import mail
from notifications.sms import is_enabled as sms_enabled
from notifications.sms import is_simulated, send_sms

from .models import PasswordResetCode, User

logger = logging.getLogger(__name__)

# A new code can be asked for after a minute, at most 5 times an hour
RESEND_AFTER = timedelta(seconds=60)
MAX_CODES_PER_HOUR = 5

MESSAGE = (
    'SAVIOR: {code} ni namba yako ya kubadilisha nenosiri (password reset code). '
    'Inaisha baada ya dakika 10. Usimpe mtu yeyote.'
)

EMAIL_SUBJECT = 'SAVIOR: namba ya kubadilisha nenosiri / password reset code'
EMAIL_TEXT = (
    'Habari {name},\n\n'
    'Namba yako ya kubadilisha nenosiri ni: {code}\n'
    'Inaisha baada ya dakika 10. Usimpe mtu yeyote.\n\n'
    'Your password reset code is: {code}\n'
    'It expires in 10 minutes. Do not share it with anyone.\n\n'
    'Kama hukuomba kubadilisha nenosiri, puuza ujumbe huu.\n'
    "If you didn't ask to reset your password, ignore this email.\n\n"
    'SAVIOR Inventory System'
)


class InvalidCode(Exception):
    """The code is wrong, used, expired, or was tried too many times."""


def request_code(phone):
    """Send a reset code to the account with this phone number, if there is one.

    The code goes by email when the user has an email address and email is set up (it is free),
    otherwise by SMS. If the email fails and SMS is set up, it goes by SMS instead.
    It does nothing for unknown numbers, so this can't be used to find out who has an account.
    Raises notifications.sms.SMSError or notifications.mail.EmailError if the code could not be sent.
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
    try:
        if user.email and mail.is_enabled():
            try:
                text = EMAIL_TEXT.format(name=user.first_name or user.phone, code=code)
                mail.send_email(user.email, EMAIL_SUBJECT, text)
                return
            except mail.EmailError:
                if not sms_enabled():
                    raise
                logger.warning('Password reset email to user %s failed; sending SMS instead', user.pk, exc_info=True)
        if is_simulated():
            print(f'\n[SMS simulation for {user.phone}] {MESSAGE.format(code=code)}\n', flush=True)
            return code
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
