import hashlib
import hmac
import json
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.testing import client_for, make_business

from . import clickpesa, sonicpesa
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
        self.assertEqual(data['days_left'], 14)

    def test_default_plans_exist(self):
        response = self.client.get('/api/subscription/plans/')
        self.assertEqual([p['code'] for p in response.data], ['monthly', 'quarterly', 'yearly'])
        self.assertEqual([p['price'] for p in response.data], ['50000.00', '141000.00', '540000.00'])

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
            {'plan': plan.pk, 'phone': '0742000001', 'provider': 'mpesa'},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(response.data['amount'], '50000.00')

        SubscriptionPayment.objects.get(pk=response.data['id']).mark_completed()
        subscription = Subscription.objects.get(business=self.business)
        self.assertEqual(subscription.status, 'active')
        self.assertTrue(subscription.is_valid)
        self.assertEqual(subscription.days_left, 30)

    def test_paying_early_keeps_remaining_days(self):
        plan = Plan.objects.get(code='monthly')
        payment = SubscriptionPayment.objects.create(
            business=self.business, plan=plan, amount=plan.price, phone='+255742000001', provider='mpesa'
        )
        payment.mark_completed()
        # 14 trial days left + 30 paid days
        self.assertEqual(Subscription.objects.get(business=self.business).days_left, 44)


@override_settings(SONICPESA_API_KEY='sk_test', SONICPESA_API_SECRET='ss_test')
class SonicPesaTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)
        self.plan = Plan.objects.get(code='monthly')

    def start_payment(self, phone='0742000001'):
        with mock.patch.object(sonicpesa, 'create_order', return_value={'order_id': 'sp_123'}) as create:
            response = self.client.post(
                '/api/subscription/payments/',
                {'plan': self.plan.pk, 'phone': phone, 'provider': 'mpesa'},
                format='json',
            )
        return response, create

    def webhook(self, payload, secret='ss_test'):
        body = json.dumps(payload).encode()
        signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        return APIClient().post(
            '/api/subscription/sonicpesa/webhook/', body,
            content_type='application/json', HTTP_X_SONICPESA_SIGNATURE=signature,
        )

    def test_payment_sends_push_ussd(self):
        response, create = self.start_payment()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['push_sent'])
        self.assertEqual(response.data['status'], 'pending')
        create.assert_called_once()
        self.assertEqual(create.call_args.kwargs['phone'], '255742000001')
        self.assertEqual(create.call_args.kwargs['amount'], 50000)
        self.assertEqual(SubscriptionPayment.objects.get().gateway_order_id, 'sp_123')

    def test_rejected_push_marks_payment_failed(self):
        with mock.patch.object(sonicpesa, 'create_order', side_effect=sonicpesa.SonicPesaError('Bad number')):
            response = self.client.post(
                '/api/subscription/payments/',
                {'plan': self.plan.pk, 'phone': '0742000001', 'provider': 'mpesa'},
                format='json',
            )
        self.assertEqual(response.status_code, 502)
        payment = SubscriptionPayment.objects.get()
        self.assertEqual(payment.status, 'failed')
        self.assertEqual(payment.failure_reason, 'Bad number')

    def test_non_tanzanian_number_is_refused(self):
        response, create = self.start_payment(phone='12345')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)
        create.assert_not_called()

    def test_number_must_match_network(self):
        # 0712... is a Mixx by Yas (Tigo Pesa) number, not M-Pesa
        response, create = self.start_payment(phone='0712000001')
        self.assertEqual(response.status_code, 400)
        self.assertIn('074, 075, 076, 079', response.data['phone'][0])
        create.assert_not_called()
        for phone in ['0742000001', '0752000001', '0762000001', '+255 792 000 001']:
            self.assertEqual(self.start_payment(phone=phone)[0].status_code, 201, phone)

    def test_manual_payment_skips_sonicpesa(self):
        with mock.patch.object(sonicpesa, 'create_order') as create:
            response = self.client.post(
                '/api/subscription/payments/',
                {'plan': self.plan.pk, 'phone': '0742000001', 'provider': 'manual'},
                format='json',
            )
        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data['push_sent'])
        create.assert_not_called()

    def test_status_check_completes_payment(self):
        payment_id = self.start_payment()[0].data['id']
        status = {'payment_status': 'SUCCESS', 'amount': 50000, 'transid': 'T1', 'channel': 'TIGOPESATZ'}
        with mock.patch.object(sonicpesa, 'order_status', return_value=status):
            response = self.client.get(f'/api/subscription/payments/{payment_id}/')
        self.assertEqual(response.data['status'], 'completed')
        self.assertEqual(response.data['provider'], 'tigopesa')
        self.assertEqual(Subscription.objects.get(business=self.business).status, 'active')

    def test_status_check_keeps_pending_and_marks_cancelled(self):
        payment_id = self.start_payment()[0].data['id']
        url = f'/api/subscription/payments/{payment_id}/'
        with mock.patch.object(sonicpesa, 'order_status', return_value={'payment_status': 'PENDING'}):
            self.assertEqual(self.client.get(url).data['status'], 'pending')
        with mock.patch.object(sonicpesa, 'order_status', side_effect=sonicpesa.SonicPesaError('down')):
            self.assertEqual(self.client.get(url).data['status'], 'pending')
        with mock.patch.object(sonicpesa, 'order_status', return_value={'payment_status': 'USERCANCELLED'}):
            self.assertEqual(self.client.get(url).data['status'], 'failed')

    def test_webhook_completes_payment_once(self):
        self.start_payment()
        payload = {'event': 'payment.success', 'order_id': 'sp_123', 'status': 'SUCCESS', 'amount': 50000}
        self.assertEqual(self.webhook(payload).status_code, 200)
        self.assertEqual(self.webhook(payload).status_code, 200)
        self.assertEqual(SubscriptionPayment.objects.get().status, 'completed')
        # 14 trial days + 30 paid days, added only once although the webhook came twice
        self.assertEqual(Subscription.objects.get(business=self.business).days_left, 44)

    def test_webhook_with_wrong_signature_is_refused(self):
        self.start_payment()
        payload = {'order_id': 'sp_123', 'status': 'SUCCESS', 'amount': 50000}
        self.assertEqual(self.webhook(payload, secret='wrong').status_code, 403)
        self.assertEqual(SubscriptionPayment.objects.get().status, 'pending')

    def test_webhook_with_too_small_amount_is_ignored(self):
        self.start_payment()
        self.webhook({'order_id': 'sp_123', 'status': 'SUCCESS', 'amount': 100})
        self.assertEqual(SubscriptionPayment.objects.get().status, 'pending')

    def test_webhook_for_unknown_order_is_ignored(self):
        response = self.webhook({'event': 'payout.success', 'data': {'withdrawal_id': 14}})
        self.assertEqual(response.status_code, 200)


@override_settings(CLICKPESA_CLIENT_ID='client', CLICKPESA_API_KEY='key', CLICKPESA_CHECKSUM_KEY='ck_test')
class ClickPesaTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)
        self.plan = Plan.objects.get(code='monthly')
        # Forget earlier status checks, so the once-a-minute limit doesn't carry over between tests
        cache.clear()

    def start_payment(self):
        with mock.patch.object(clickpesa, 'create_control_number', return_value='55042914871931') as create:
            response = self.client.post(
                '/api/subscription/payments/', {'plan': self.plan.pk, 'provider': 'controlnumber'}, format='json'
            )
        return response, create

    def webhook(self, data, key='ck_test'):
        with self.settings(CLICKPESA_CHECKSUM_KEY=key):
            data = {**data, 'checksum': clickpesa.checksum(data)}
        return APIClient().post(
            '/api/subscription/clickpesa/webhook/', {'event': 'PAYMENT RECEIVED', 'data': data}, format='json'
        )

    def paid(self, **extra):
        return {
            'status': 'SUCCESS', 'orderReference': '55042914871931', 'paymentReference': 'P1',
            'collectedAmount': '50000', 'channel': 'AIRTEL-MONEY', **extra,
        }

    def test_control_number_is_made_without_a_phone(self):
        response, create = self.start_payment()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data['control_number'], '55042914871931')
        self.assertEqual(response.data['status'], 'pending')
        self.assertEqual(response.data['phone'], '')
        self.assertEqual(create.call_args.kwargs['amount'], 50000)

    def test_subscription_says_control_numbers_are_on(self):
        self.assertTrue(self.client.get('/api/subscription/').data['control_numbers']['enabled'])
        with self.settings(CLICKPESA_API_KEY=''):
            self.assertFalse(self.client.get('/api/subscription/').data['control_numbers']['enabled'])

    def test_refused_when_clickpesa_is_off(self):
        with self.settings(CLICKPESA_API_KEY=''):
            response = self.start_payment()[0]
        self.assertEqual(response.status_code, 400)
        self.assertIn('provider', response.data)
        self.assertFalse(SubscriptionPayment.objects.exists())

    def test_clickpesa_error_marks_payment_failed(self):
        with mock.patch.object(clickpesa, 'create_control_number', side_effect=clickpesa.ClickPesaError('Down')):
            response = self.client.post(
                '/api/subscription/payments/', {'plan': self.plan.pk, 'provider': 'controlnumber'}, format='json'
            )
        self.assertEqual(response.status_code, 502)
        self.assertEqual(SubscriptionPayment.objects.get().status, 'failed')

    def test_status_check_completes_payment(self):
        payment_id = self.start_payment()[0].data['id']
        url = f'/api/subscription/payments/{payment_id}/'
        with mock.patch.object(clickpesa, 'payment_status', return_value=[]):
            self.assertEqual(self.client.get(url).data['status'], 'pending')
        # A failed attempt leaves the control number open, so the payer can try again
        cache.clear()
        with mock.patch.object(clickpesa, 'payment_status', return_value=[self.paid(status='FAILED')]):
            self.assertEqual(self.client.get(url).data['status'], 'pending')
        cache.clear()
        with mock.patch.object(clickpesa, 'payment_status', return_value=[self.paid()]) as status:
            response = self.client.get(url)
        status.assert_called_once_with('55042914871931')
        self.assertEqual(response.data['status'], 'completed')
        self.assertEqual(response.data['provider'], 'airtelmoney')
        self.assertEqual(Subscription.objects.get(business=self.business).days_left, 44)

    def test_status_checks_are_limited_to_one_a_minute(self):
        payment_id = self.start_payment()[0].data['id']
        with mock.patch.object(clickpesa, 'payment_status', return_value=[]) as status:
            for _ in range(3):
                self.client.get(f'/api/subscription/payments/{payment_id}/')
        status.assert_called_once()

    def test_webhook_completes_payment_once(self):
        self.start_payment()
        self.assertEqual(self.webhook(self.paid()).status_code, 200)
        self.assertEqual(self.webhook(self.paid()).status_code, 200)
        payment = SubscriptionPayment.objects.get()
        self.assertEqual(payment.status, 'completed')
        self.assertEqual(payment.gateway_transid, 'P1')
        self.assertEqual(Subscription.objects.get(business=self.business).days_left, 44)

    def test_webhook_with_wrong_checksum_is_refused(self):
        self.start_payment()
        self.assertEqual(self.webhook(self.paid(), key='wrong').status_code, 403)
        self.assertEqual(SubscriptionPayment.objects.get().status, 'pending')

    def test_webhook_with_too_small_amount_is_ignored(self):
        self.start_payment()
        self.webhook(self.paid(collectedAmount='100'))
        self.assertEqual(SubscriptionPayment.objects.get().status, 'pending')

    def test_webhook_for_unknown_number_is_ignored(self):
        self.assertEqual(self.webhook(self.paid(orderReference='999', paymentReference='X')).status_code, 200)

    def test_checksum_sorts_keys_at_every_level(self):
        a = {'b': 1, 'a': {'d': 'x', 'c': [{'f': 2, 'e': 3}]}}
        b = {'a': {'c': [{'e': 3, 'f': 2}], 'd': 'x'}, 'b': 1, 'checksumMethod': 'canonical'}
        with self.settings(CLICKPESA_CHECKSUM_KEY='k'):
            self.assertEqual(clickpesa.checksum(a), clickpesa.checksum(b))
