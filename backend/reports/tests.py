from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from accounts.testing import client_for, make_business
from expenses.models import Expense
from inventory.models import Product


class ReportTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)
        product = Product.objects.create(
            business=self.business, name='Mafuta 1L', cost_price=4000, selling_price=5000, stock_quantity=20
        )
        self.client.post('/api/sales/', {'items': [{'product': product.pk, 'quantity': '4'}]}, format='json')
        self.client.post('/api/expenses/', {'category': 'transport', 'amount': '1500'}, format='json')

    def test_profit_and_loss(self):
        response = self.client.get('/api/reports/summary/?period=today')
        self.assertEqual(response.status_code, 200, response.data)
        totals = response.data['totals']
        self.assertEqual(totals['revenue'], Decimal('20000'))
        self.assertEqual(totals['cost_of_goods'], Decimal('16000'))
        self.assertEqual(totals['gross_profit'], Decimal('4000'))
        self.assertEqual(totals['expenses'], Decimal('1500'))
        self.assertEqual(totals['net_profit'], Decimal('2500'))
        self.assertEqual(response.data['top_products'][0]['product_name'], 'Mafuta 1L')

    def test_dashboard(self):
        response = self.client.get('/api/reports/dashboard/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['today']['sales_count'], 1)
        self.assertEqual(len(response.data['last_7_days']), 7)
        self.assertEqual(response.data['stock']['product_count'], 1)

    def test_other_business_data_not_included(self):
        _, other_owner = make_business('Duka B', '+255712000002')
        totals = client_for(other_owner).get('/api/reports/summary/?period=today').data['totals']
        self.assertEqual(totals['revenue'], 0)
        self.assertEqual(Expense.objects.count(), 1)

    def test_staff_cannot_see_reports(self):
        staff = User.objects.create_user(
            phone='+255655000111', password='x', business=self.business, role=User.Role.STAFF
        )
        self.assertEqual(client_for(staff).get('/api/reports/summary/').status_code, 403)

    def test_bad_date_gives_clear_error(self):
        response = self.client.get('/api/reports/summary/?start=26-10-2026')
        self.assertEqual(response.status_code, 400)
        self.assertIn('start', response.data)
