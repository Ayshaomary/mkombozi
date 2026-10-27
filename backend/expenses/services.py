from django.db import transaction

from notifications.models import Notification
from notifications.services import notify

from .models import Expense, RecurringExpense

# Safety limit: at most this many missed repeats are recorded in one go (e.g. a year of daily expenses)
MAX_CATCH_UP = 400


@transaction.atomic
def process_recurring_expenses(business, today, queryset=None):
    """Record every recurring expense that is due up to `today`, including missed ones.

    Safe to run many times: each repeat is recorded once, because `occurrences` moves forward.
    Returns the number of expenses created.
    """
    due = (queryset if queryset is not None else RecurringExpense.objects.all()).filter(
        business=business, is_active=True, next_date__lte=today
    )
    created = 0
    for recurring in due.select_for_update():
        for _ in range(MAX_CATCH_UP):
            if recurring.next_date > today:
                break
            expense = Expense.objects.create(
                business=business,
                category=recurring.category,
                amount=recurring.amount,
                description=recurring.description,
                date=recurring.next_date,
                recurring=recurring,
                created_by=recurring.created_by,
            )
            recurring.occurrences += 1
            recurring.save()  # also moves next_date forward
            created += 1
            notify(
                business,
                Notification.Kind.RECURRING_EXPENSE,
                {
                    'category': expense.category,
                    'amount': str(expense.amount),
                    'description': expense.description,
                    'date': expense.date.isoformat(),
                },
                audience=Notification.Audience.OWNER,
                dedupe_key=f'recurring:{recurring.pk}:{expense.date.isoformat()}',
            )
    return created
