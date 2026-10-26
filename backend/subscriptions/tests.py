from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from accounts.testing import client_for, make_business

from .models import Plan, Subscription, SubscriptionPayment


class SubscriptionTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)

    def expire(self):
        subscription = self.business.subscription
        subscription.current_period_end = timezone.now() - timedelta(days=1)
        subscription.save()

    def test_new_business_has_trial(self):
        data = self.client.get('/api/subscription/').data
        self.assertEqual(data['status'], 'trial')
        self.assertTrue(data['is_valid'])
        self.assertIn(data['days_left'], (13, 14))

    def test_default_plans_exist(self):
        response = self.client.get('/api/subscription/plans/')
        self.assertEqual([p['code'] for p in response.data], ['monthly', 'quarterly', 'yearly'])

    def test_expired_can_view_but_not_add(self):
        self.expire()
        self.assertEqual(self.client.get('/api/products/').status_code, 200)
        response = self.client.post('/api/products/', {'name': 'X', 'cost_price': 1, 'selling_price': 2})
        self.assertEqual(response.status_code, 403)

    def test_confirmed_payment_reactivates_and_adds_days(self):
        self.expire()
        plan = Plan.objects.get(code='monthly')
        response = self.client.post(
            '/api/subscription/payments/',
            {'plan': plan.pk, 'phone': '0712000001', 'provider': 'mpesa'},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(response.data['amount'], '10000.00')

        SubscriptionPayment.objects.get(pk=response.data['id']).mark_completed()
        subscription = Subscription.objects.get(business=self.business)
        self.assertEqual(subscription.status, 'active')
        self.assertTrue(subscription.is_valid)
        self.assertIn(subscription.days_left, (29, 30))

    def test_paying_early_keeps_remaining_days(self):
        plan = Plan.objects.get(code='monthly')
        payment = SubscriptionPayment.objects.create(
            business=self.business, plan=plan, amount=plan.price, phone='+255712000001', provider='mpesa'
        )
        payment.mark_completed()
        # 14 trial days left + 30 paid days
        self.assertIn(Subscription.objects.get(business=self.business).days_left, (43, 44))
