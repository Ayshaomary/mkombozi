"""Automatic tasks: recurring expenses, the daily summary and subscription reminders.

They run in two ways:
  1. Whenever someone from the business opens the app (at most once every RUN_EVERY), so they work
     even on a free server that sleeps. Missed days are caught up on the next visit.
  2. With `python manage.py run_automations`, which a scheduled job (cron) can run every morning.
Every task is safe to run many times: nothing is ever recorded or sent twice.
"""

from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from accounts.models import Business
from expenses.services import process_recurring_expenses
from reports.services import totals

from .models import Notification
from .services import notify

RUN_EVERY = timedelta(minutes=15)
# Remind the owner when this many days (or fewer) are left; one reminder per step
REMINDER_DAYS = (7, 3, 1)


def send_daily_summary(business, today):
    """Yesterday's numbers for the owner, once per day, only if anything happened."""
    yesterday = today - timedelta(days=1)
    key = f'daily_summary:{yesterday.isoformat()}'
    if Notification.objects.filter(business=business, dedupe_key=key).exists():
        return None
    day = totals(business, yesterday, yesterday)
    if not day['sales_count'] and not day['expenses']:
        return None
    data = {'date': yesterday.isoformat(), 'sales_count': day['sales_count']}
    data.update({field: str(day[field]) for field in ('revenue', 'gross_profit', 'expenses', 'net_profit')})
    return notify(business, Notification.Kind.DAILY_SUMMARY, data, Notification.Audience.OWNER, key)


def check_subscription(business):
    """Remind the owner before the trial or subscription ends, and when it has ended."""
    subscription = getattr(business, 'subscription', None)
    if subscription is None:
        return None
    end = subscription.current_period_end.date().isoformat()
    data = {'status': subscription.status, 'end': end}
    if not subscription.is_valid:
        return notify(
            business, Notification.Kind.SUBSCRIPTION_EXPIRED, data, Notification.Audience.OWNER,
            f'subscription_expired:{end}',
        )
    days_left = subscription.days_left
    steps = [days for days in REMINDER_DAYS if days_left <= days]
    if not steps:
        return None
    # Only the closest step, so opening the app with 2 days left doesn't also send the 7-day reminder
    step = min(steps)
    return notify(
        business, Notification.Kind.SUBSCRIPTION_ENDING, {**data, 'days_left': days_left},
        Notification.Audience.OWNER, f'subscription_ending:{end}:{step}',
    )


def run_automations(business, force=False):
    """Run all automatic tasks for one business. Returns True if they ran, False if skipped (ran recently)."""
    now = timezone.now()
    # Quick check without locking, so most app requests return immediately
    if not force and business.automations_ran_at and now - business.automations_ran_at < RUN_EVERY:
        return False
    with transaction.atomic():
        # Lock the business so two requests at the same moment don't both do the work
        locked = Business.objects.select_for_update().get(pk=business.pk)
        if not force and locked.automations_ran_at and now - locked.automations_ran_at < RUN_EVERY:
            return False
        today = timezone.localdate()
        process_recurring_expenses(locked, today)
        send_daily_summary(locked, today)
        check_subscription(locked)
        locked.automations_ran_at = now
        locked.save(update_fields=['automations_ran_at'])
    business.automations_ran_at = now
    return True
