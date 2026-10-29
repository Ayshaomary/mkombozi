from datetime import date, timedelta
from decimal import Decimal
import json
from io import StringIO
from unittest import mock

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts.models import User
from accounts.testing import client_for, make_business
from expenses.models import Expense, RecurringExpense, nth_occurrence
from inventory.models import Product, StockMovement
from inventory.services import change_stock

from . import mail
from .automations import check_subscription, run_automations, send_daily_summary
from .models import Notification


class StockAlertTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.product = Product.objects.create(
            business=self.business, name='Sukari', cost_price=2800, selling_price=3200,
            stock_quantity=10, low_stock_threshold=5,
        )

    def kinds(self):
        return list(Notification.objects.order_by('id').values_list('kind', flat=True))

    def test_alert_once_when_crossing_the_warning_level(self):
        change_stock(self.product, Decimal('-4'), StockMovement.Type.SALE)  # 10 -> 6: still fine
        self.assertEqual(self.kinds(), [])
        change_stock(self.product, Decimal('-2'), StockMovement.Type.SALE)  # 6 -> 4: crosses 5
        change_stock(self.product, Decimal('-1'), StockMovement.Type.SALE)  # 4 -> 3: already low
        self.assertEqual(self.kinds(), ['low_stock'])
        notification = Notification.objects.get()
        self.assertEqual(notification.data['name'], 'Sukari')
        self.assertEqual(notification.audience, 'all')

    def test_out_of_stock_alert_and_alert_again_after_restock(self):
        change_stock(self.product, Decimal('-10'), StockMovement.Type.SALE)  # 10 -> 0
        self.assertEqual(self.kinds(), ['out_of_stock'])
        change_stock(self.product, Decimal('20'), StockMovement.Type.PURCHASE)  # restocked
        change_stock(self.product, Decimal('-16'), StockMovement.Type.SALE)  # 20 -> 4: crosses again
        self.assertEqual(self.kinds(), ['out_of_stock', 'low_stock'])

    def test_failed_sale_creates_no_alert(self):
        response = client_for(self.owner).post(
            '/api/sales/', {'items': [{'product': self.product.pk, 'quantity': '50'}]}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.kinds(), [])


class RecurringExpenseTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)
        self.today = timezone.localdate()

    def create(self, **overrides):
        data = {'category': 'rent', 'amount': '150000', 'frequency': 'monthly', 'start_date': self.today.isoformat(), **overrides}
        return self.client.post('/api/recurring-expenses/', data, format='json')

    def test_due_today_is_recorded_immediately(self):
        response = self.create()
        self.assertEqual(response.status_code, 201, response.data)
        expense = Expense.objects.get()
        self.assertEqual(expense.amount, 150000)
        self.assertEqual(expense.recurring_id, response.data['id'])
        self.assertGreater(response.data['next_date'], self.today.isoformat())
        self.assertEqual(Notification.objects.get().kind, 'recurring_expense')

    def test_missed_weeks_are_caught_up_once(self):
        self.create(frequency='weekly', amount='5000', start_date=(self.today - timedelta(days=20)).isoformat())
        self.assertEqual(Expense.objects.count(), 3)  # 20, 13 and 6 days ago
        run_automations(self.business, force=True)
        run_automations(self.business, force=True)
        self.assertEqual(Expense.objects.count(), 3)

    def test_future_start_records_nothing_yet(self):
        self.create(start_date=(self.today + timedelta(days=3)).isoformat())
        self.assertEqual(Expense.objects.count(), 0)

    def test_month_end_dates(self):
        dates = [nth_occurrence(date(2026, 1, 31), 'monthly', n) for n in range(4)]
        self.assertEqual(dates, [date(2026, 1, 31), date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)])

    def test_paused_is_skipped(self):
        RecurringExpense.objects.create(business=self.business, amount=1000, start_date=self.today, is_active=False)
        run_automations(self.business, force=True)
        self.assertEqual(Expense.objects.count(), 0)

    def test_start_date_cannot_be_more_than_a_year_ago(self):
        response = self.create(start_date=(self.today - timedelta(days=400)).isoformat())
        self.assertEqual(response.status_code, 400)
        self.assertIn('start_date', response.data)

    def test_staff_cannot_manage_recurring_expenses(self):
        staff = User.objects.create_user(phone='+255655000111', password='x', business=self.business, role=User.Role.STAFF)
        self.assertEqual(client_for(staff).get('/api/recurring-expenses/').status_code, 403)


class DailySummaryTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.today = timezone.localdate()

    def test_summary_of_yesterday_once(self):
        Expense.objects.create(business=self.business, category='transport', amount=5000, date=self.today - timedelta(days=1))
        send_daily_summary(self.business, self.today)
        send_daily_summary(self.business, self.today)
        summary = Notification.objects.get(kind='daily_summary')
        self.assertEqual(summary.data['expenses'], '5000.00')
        self.assertEqual(summary.data['net_profit'], '-5000.00')
        self.assertEqual(summary.audience, 'owner')

    def test_no_summary_for_a_quiet_day(self):
        self.assertIsNone(send_daily_summary(self.business, self.today))


class SubscriptionReminderTests(TestCase):
    """The subscription end date stays fixed; we move 'now' forward to simulate days passing."""

    def setUp(self):
        self.business, self.owner = make_business()
        self.start = timezone.now()
        subscription = self.business.subscription
        subscription.current_period_end = self.start + timedelta(days=10)
        subscription.save()

    def check_on_day(self, day):
        with mock.patch('django.utils.timezone.now', return_value=self.start + timedelta(days=day)):
            check_subscription(self.business)

    def steps(self):
        return [key.rsplit(':', 1)[1] for key in Notification.objects.order_by('id').values_list('dedupe_key', flat=True)]

    def test_one_reminder_per_step_without_repeats(self):
        for day in [0, 4, 5, 5, 8, 9, 9.5]:  # 10, 6, 5, 5, 2, 1 and 0.5 days left
            self.check_on_day(day)
        self.assertEqual(self.steps(), ['7', '3', '1'])
        self.assertEqual(Notification.objects.first().audience, 'owner')

    def test_opening_late_skips_older_steps(self):
        self.check_on_day(8.5)  # 1.5 days left: only the 3-day reminder, not the 7-day one too
        self.assertEqual(self.steps(), ['3'])

    def test_expired_reminder_once(self):
        self.check_on_day(11)
        self.check_on_day(12)
        self.assertEqual(list(Notification.objects.values_list('kind', flat=True)), ['subscription_expired'])


class NotificationApiTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.staff = User.objects.create_user(phone='+255655000111', password='x', business=self.business, role=User.Role.STAFF)
        Notification.objects.create(business=self.business, kind='low_stock', data={'name': 'Chumvi'})
        Notification.objects.create(business=self.business, kind='daily_summary', audience='owner', data={})

    def test_owner_sees_all_staff_sees_only_shared(self):
        owner_data = client_for(self.owner).get('/api/notifications/').data
        staff_data = client_for(self.staff).get('/api/notifications/').data
        self.assertEqual(owner_data['unread_count'], 2)
        self.assertEqual([n['kind'] for n in staff_data['results']], ['low_stock'])

    def test_mark_read(self):
        client = client_for(self.owner)
        first = Notification.objects.first()
        self.assertTrue(client.post(f'/api/notifications/{first.pk}/read/').data['is_read'])
        client.post('/api/notifications/read-all/')
        self.assertEqual(client.get('/api/notifications/').data['unread_count'], 0)

    def test_other_business_cannot_see_or_read(self):
        _, other_owner = make_business('Duka B', '+255712000002')
        other = client_for(other_owner)
        self.assertEqual(other.get('/api/notifications/').data['count'], 0)
        self.assertEqual(other.post(f'/api/notifications/{Notification.objects.first().pk}/read/').status_code, 404)

    def test_opening_the_list_runs_automations_at_most_every_15_minutes(self):
        today = timezone.localdate()
        RecurringExpense.objects.create(business=self.business, amount=1000, start_date=today, frequency='daily')
        client = client_for(self.owner)
        client.get('/api/notifications/')
        self.assertEqual(Expense.objects.count(), 1)

        # Ran just now, so a new due expense is not processed yet
        RecurringExpense.objects.create(business=self.business, amount=2000, start_date=today, frequency='daily')
        client.get('/api/notifications/')
        self.assertEqual(Expense.objects.count(), 1)

        self.business.__class__.objects.filter(pk=self.business.pk).update(
            automations_ran_at=timezone.now() - timedelta(minutes=16)
        )
        client_for(User.objects.get(pk=self.owner.pk)).get('/api/notifications/')
        self.assertEqual(Expense.objects.count(), 2)

    def test_management_command(self):
        RecurringExpense.objects.create(business=self.business, amount=1000, start_date=timezone.localdate(), frequency='monthly')
        call_command('run_automations', stdout=StringIO())
        self.assertEqual(Expense.objects.count(), 1)


@override_settings(BREVO_API_KEY='brevo-key', EMAIL_FROM='savior@example.com', EMAIL_FROM_NAME='SAVIOR')
class EmailTests(TestCase):
    def test_sends_through_brevo_api(self):
        with mock.patch.object(mail.request, 'urlopen') as urlopen:
            mail.send_email('juma@example.com', 'Hello', 'Code 123456')
        sent = urlopen.call_args.args[0]
        self.assertEqual(sent.full_url, 'https://api.brevo.com/v3/smtp/email')
        self.assertEqual(sent.get_header('Api-key'), 'brevo-key')
        self.assertEqual(json.loads(sent.data), {
            'sender': {'name': 'SAVIOR', 'email': 'savior@example.com'},
            'to': [{'email': 'juma@example.com'}],
            'subject': 'Hello',
            'textContent': 'Code 123456',
        })

    def test_brevo_refusal_raises_email_error(self):
        with mock.patch.object(mail.request, 'urlopen', side_effect=mail.error.URLError('down')):
            with self.assertRaises(mail.EmailError):
                mail.send_email('juma@example.com', 'Hello', 'Code')
