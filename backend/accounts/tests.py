from django.test import TestCase
from rest_framework.test import APIClient

from .models import User
from .testing import client_for, make_business
from .utils import normalize_phone


class PhoneNormalizationTests(TestCase):
    def test_tanzanian_formats_become_one(self):
        for raw in ['0712345678', '0712 345 678', '255712345678', '+255712345678', '+255 712-345-678']:
            self.assertEqual(normalize_phone(raw), '+255712345678')


class RegisterAndLoginTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def register(self, **overrides):
        data = {
            'business_name': 'Duka la Amina',
            'first_name': 'Amina',
            'phone': '0754111222',
            'password': 'Mukombozi2026!',
            **overrides,
        }
        return self.client.post('/api/auth/register/', data, format='json')

    def test_register_creates_business_owner_and_trial(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertIn('access', response.data)
        user = User.objects.get(phone='+255754111222')
        self.assertEqual(user.role, User.Role.OWNER)
        self.assertEqual(user.business.name, 'Duka la Amina')
        self.assertTrue(user.business.subscription.is_valid)

    def test_duplicate_phone_rejected_in_any_format(self):
        self.register()
        response = self.register(phone='+255 754 111 222')
        self.assertEqual(response.status_code, 400)
        self.assertIn('phone', response.data)

    def test_login_with_different_phone_format(self):
        self.register()
        response = self.client.post(
            '/api/auth/login/', {'phone': '255754111222', 'password': 'Mukombozi2026!'}, format='json'
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertIn('access', response.data)
        self.assertEqual(response.data['user']['business']['name'], 'Duka la Amina')

    def test_wrong_password_rejected(self):
        self.register()
        response = self.client.post(
            '/api/auth/login/', {'phone': '0754111222', 'password': 'wrong-password'}, format='json'
        )
        self.assertEqual(response.status_code, 401)


class StaffTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()

    def test_owner_adds_staff_who_cannot_manage_staff(self):
        response = client_for(self.owner).post(
            '/api/staff/',
            {'first_name': 'Neema', 'phone': '0655000111', 'password': 'Muuzaji2026!'},
            format='json',
        )
        self.assertEqual(response.status_code, 201, response.data)
        staff = User.objects.get(phone='+255655000111')
        self.assertEqual(staff.role, User.Role.STAFF)
        self.assertEqual(staff.business, self.business)
        self.assertEqual(client_for(staff).get('/api/staff/').status_code, 403)

    def test_owner_cannot_delete_themselves(self):
        response = client_for(self.owner).delete(f'/api/staff/{self.owner.pk}/')
        self.assertEqual(response.status_code, 404)
        self.assertTrue(User.objects.filter(pk=self.owner.pk).exists())
