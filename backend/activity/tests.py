from unittest import mock

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from accounts import password_reset
from accounts.testing import client_for, make_business

from .models import ActivityLog


class ActivityLogTests(TestCase):
    def setUp(self):
        cache.clear()
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)

    def last(self):
        return ActivityLog.objects.first()

    def test_adding_changing_and_deleting_are_logged(self):
        response = self.client.post(
            '/api/products/', {'name': 'Sukari', 'cost_price': 2500, 'selling_price': 3000}, format='json'
        )
        product_id = response.data['id']
        entry = self.last()
        self.assertEqual((entry.action, entry.summary), ('create', 'Added product Sukari'))
        self.assertEqual((entry.user, entry.business), (self.owner, self.business))

        self.client.patch(f'/api/products/{product_id}/', {'selling_price': 3200}, format='json')
        self.assertEqual(self.last().summary, 'Changed product Sukari')

        self.client.post(
            f'/api/products/{product_id}/stock/', {'movement_type': 'purchase', 'quantity': '10'}, format='json'
        )
        self.assertEqual(self.last().action, 'other')
        self.assertTrue(self.last().summary.startswith('Stock: product'))

        sale = self.client.post(
            '/api/sales/', {'items': [{'product': product_id, 'quantity': '2'}], 'payment_method': 'cash'},
            format='json',
        )
        self.assertEqual(sale.status_code, 201, sale.data)
        self.assertEqual(self.last().summary, f'Added sale {sale.data["receipt_number"]} (TZS 6,400)')

        self.client.delete(f'/api/products/{product_id}/')
        self.assertEqual((self.last().action, self.last().summary), ('delete', f'Deleted product #{product_id}'))

    def test_reading_is_not_logged(self):
        self.client.get('/api/products/')
        self.client.get('/api/sales/')
        self.assertFalse(ActivityLog.objects.exists())

    def test_login_and_failed_login_are_logged(self):
        client = APIClient(REMOTE_ADDR='41.59.1.2')
        client.post('/api/auth/login/', {'phone': '0712000001', 'password': 'siri-kali-123'}, format='json')
        entry = self.last()
        self.assertEqual((entry.action, entry.user, entry.ip_address), ('login', self.owner, '41.59.1.2'))

        response = client.post('/api/auth/login/', {'phone': '0712000001', 'password': 'wrong'}, format='json')
        self.assertEqual(response.status_code, 401)
        entry = self.last()
        self.assertEqual((entry.action, entry.user), ('login_failed', self.owner))
        self.assertEqual(entry.summary, 'Failed login for 0712000001')

    def test_password_reset_is_linked_to_the_user(self):
        with mock.patch.object(password_reset, 'send_sms'):
            APIClient().post('/api/auth/password-reset/', {'phone': '0712000001'}, format='json')
        entry = self.last()
        self.assertEqual((entry.action, entry.user), ('password', self.owner))

    def test_failed_changes_are_not_logged(self):
        self.client.post('/api/products/', {'name': ''})
        self.assertFalse(ActivityLog.objects.exists())


class ActivityAdminTests(TestCase):
    def test_admin_pages_show_the_log(self):
        from accounts.models import User

        business, owner = make_business()
        client_for(owner).post('/api/categories/', {'name': 'Vinywaji'}, format='json')
        admin_user = User.objects.create_superuser(phone='0745111222', password='Msimamizi2026!', first_name='Admin')
        self.client.force_login(admin_user)
        page = self.client.get('/admin/activity/activitylog/')
        self.assertContains(page, 'Added category Vinywaji')
        self.assertContains(self.client.get('/admin/accounts/user/'), 'View activity')
        self.assertContains(self.client.get('/admin/accounts/business/'), 'View activity')
        self.assertContains(self.client.get(f'/admin/activity/activitylog/?user__id__exact={owner.pk}'), 'Vinywaji')
