from datetime import date, timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError


def parse_date(value, name):
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValidationError({name: 'Use the format YYYY-MM-DD, e.g. 2026-10-26.'})


def date_range_from_params(params, default=None):
    """Read ?start=YYYY-MM-DD&end=YYYY-MM-DD or ?period=today|week|month|year.

    Returns (start, end) as dates, or (None, None) if nothing was given and there is no default.
    """
    period = params.get('period') or (None if params.get('start') or params.get('end') else default)
    today = timezone.localdate()
    if period == 'today':
        return today, today
    if period == 'week':
        return today - timedelta(days=today.weekday()), today
    if period == 'month':
        return today.replace(day=1), today
    if period == 'year':
        return today.replace(month=1, day=1), today
    if period:
        raise ValidationError({'period': 'Choose today, week, month or year.'})

    start = parse_date(params['start'], 'start') if params.get('start') else None
    end = parse_date(params['end'], 'end') if params.get('end') else None
    if start and end and start > end:
        raise ValidationError({'start': 'Start date must be before end date.'})
    return start, end
