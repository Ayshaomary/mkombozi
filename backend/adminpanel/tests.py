from django.test import TestCase

from accounts.models import User
from accounts.testing import client_for, make_business
from activity.models import ActivityLog


class AdminDashboardTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.staff = User.objects.create_user(
            phone='0712000002', password='siri-kali-123', first_name='Neema', business=self.business, role='staff'
        )
        self.admin = User.objects.create_superuser(phone='0745111222', password='Msimamizi2026!', first_name='Admin')
        self.client = client_for(self.admin)

    def patch(self, user, client=None, **data):
        return (client or self.client).patch(f'/api/admin/users/{user.pk}/', data, format='json')

    def test_only_admins_can_use_it(self):
        for url in ['/api/admin/overview/', '/api/admin/activities/', '/api/admin/users/', '/api/admin/businesses/']:
            self.assertEqual(client_for(self.owner).get(url).status_code, 403, url)
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertEqual(self.patch(self.staff, client=client_for(self.owner), role='owner').status_code, 403)

    def test_overview_counts(self):
        data = self.client.get('/api/admin/overview/').data
        self.assertEqual(data['businesses'], 1)
        self.assertEqual(data['users'], 2)  # the admin has no shop, so isn't counted
        self.assertEqual(data['subscriptions']['trial'], 1)
        self.assertEqual(data['recent_businesses'][0]['name'], 'Duka la Juma')

    def test_sees_everyones_activity_and_filters_it(self):
        client_for(self.owner).post('/api/categories/', {'name': 'Vinywaji'}, format='json')
        other_business, other_owner = make_business(name='Duka B', phone='0712000009')
        client_for(other_owner).post('/api/categories/', {'name': 'Saruji'}, format='json')

        results = self.client.get('/api/admin/activities/').data['results']
        self.assertEqual([r['summary'] for r in results], ['Added category Saruji', 'Added category Vinywaji'])
        self.assertEqual(results[0]['business_name'], 'Duka B')

        filtered = self.client.get('/api/admin/activities/', {'business': self.business.pk}).data['results']
        self.assertEqual([r['summary'] for r in filtered], ['Added category Vinywaji'])
        self.assertEqual(len(self.client.get('/api/admin/activities/', {'search': 'saruji'}).data['results']), 1)

    def test_lists_and_filters_users(self):
        phones = [u['phone'] for u in self.client.get('/api/admin/users/', {'role': 'staff'}).data['results']]
        self.assertEqual(phones, ['+255712000002'])
        admins = self.client.get('/api/admin/users/', {'role': 'admin'}).data['results']
        self.assertEqual([u['phone'] for u in admins], ['+255745111222'])
        self.assertEqual(len(self.client.get('/api/admin/users/', {'search': 'neema'}).data['results']), 1)

    def test_change_role_is_saved_and_logged(self):
        response = self.patch(self.staff, role='owner')
        self.assertEqual(response.status_code, 200, response.data)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.role, 'owner')
        entry = ActivityLog.objects.first()
        self.assertEqual(entry.user, self.admin)
        self.assertEqual(entry.summary, 'Admin changed Neema (+255712000002): role staff → owner')

    def test_shop_keeps_an_active_owner(self):
        self.assertEqual(self.patch(self.owner, role='staff').status_code, 400)
        self.assertEqual(self.patch(self.owner, is_active=False).status_code, 400)
        # Once someone else is owner, the first owner can become staff
        self.patch(self.staff, role='owner')
        self.assertEqual(self.patch(self.owner, role='staff').status_code, 200)

    def test_cannot_lock_yourself_out(self):
        self.assertEqual(self.patch(self.admin, is_staff=False).status_code, 400)
        self.assertEqual(self.patch(self.admin, is_active=False).status_code, 400)

    def test_only_superusers_give_admin_access(self):
        helper = User.objects.create_user(phone='0745111333', password='Msaidizi2026!', first_name='Msaidizi', is_staff=True)
        helper_client = client_for(helper)
        self.assertEqual(self.patch(self.staff, client=helper_client, is_staff=True).status_code, 400)
        self.assertEqual(self.patch(self.admin, client=helper_client, is_active=False).status_code, 400)
        # A helper admin can still change shop roles
        self.assertEqual(self.patch(self.staff, client=helper_client, role='owner').status_code, 200)
        self.assertEqual(self.patch(self.staff, is_staff=True).status_code, 200)

    def test_me_shows_admin_flags_but_cannot_change_them(self):
        client = client_for(self.owner)
        self.assertFalse(client.get('/api/auth/me/').data['is_staff'])
        client.patch('/api/auth/me/', {'is_staff': True, 'is_superuser': True}, format='json')
        self.owner.refresh_from_db()
        self.assertFalse(self.owner.is_staff or self.owner.is_superuser)
