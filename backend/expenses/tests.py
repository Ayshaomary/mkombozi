from django.test import TestCase

from accounts.models import User
from accounts.testing import client_for, make_business

from .models import Expense


class ExpenseTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)

    def test_create_and_filter_by_date(self):
        self.client.post('/api/expenses/', {'category': 'rent', 'amount': '150000', 'date': '2026-09-01'})
        self.client.post('/api/expenses/', {'category': 'transport', 'amount': '5000', 'date': '2026-10-05'})
        response = self.client.get('/api/expenses/?start=2026-10-01&end=2026-10-31')
        self.assertEqual(response.data['count'], 1)
        self.assertEqual(response.data['results'][0]['category'], 'transport')
        self.assertEqual(response.data['total'], 5000)

    def test_amount_must_be_positive(self):
        response = self.client.post('/api/expenses/', {'category': 'rent', 'amount': '-10'})
        self.assertEqual(response.status_code, 400)

    def test_staff_can_add_but_not_delete(self):
        staff = User.objects.create_user(
            phone='+255655000111', password='x', business=self.business, role=User.Role.STAFF
        )
        staff_client = client_for(staff)
        response = staff_client.post('/api/expenses/', {'category': 'transport', 'amount': '2000'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(staff_client.delete(f"/api/expenses/{response.data['id']}/").status_code, 403)
        self.assertEqual(Expense.objects.count(), 1)
