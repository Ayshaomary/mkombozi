from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from accounts.testing import client_for, make_business
from inventory.models import Product, StockMovement

from .models import Sale


class SaleTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)
        self.sugar = Product.objects.create(
            business=self.business, name='Sukari 1kg', cost_price=2800, selling_price=3200, stock_quantity=10
        )
        self.soap = Product.objects.create(
            business=self.business, name='Sabuni', cost_price=1000, selling_price=1500, stock_quantity=5
        )

    def sell(self, items, **extra):
        return self.client.post('/api/sales/', {'items': items, 'payment_method': 'mpesa', **extra}, format='json')

    def test_sale_reduces_stock_and_calculates_profit(self):
        response = self.sell([
            {'product': self.sugar.pk, 'quantity': '2'},
            {'product': self.soap.pk, 'quantity': '1', 'unit_price': '1400'},
        ], discount='400')
        self.assertEqual(response.status_code, 201, response.data)
        # 2 x 3200 + 1 x 1400 - 400 discount = 7400; cost = 2 x 2800 + 1000 = 6600
        self.assertEqual(Decimal(response.data['total_amount']), 7400)
        self.assertEqual(Decimal(response.data['total_cost']), 6600)
        self.assertEqual(Decimal(response.data['profit']), 800)
        self.assertEqual(response.data['receipt_number'], 'R00001')

        self.sugar.refresh_from_db()
        self.soap.refresh_from_db()
        self.assertEqual(self.sugar.stock_quantity, 8)
        self.assertEqual(self.soap.stock_quantity, 4)
        self.assertEqual(StockMovement.objects.filter(movement_type='sale').count(), 2)

    def test_not_enough_stock_saves_nothing(self):
        response = self.sell([
            {'product': self.sugar.pk, 'quantity': '1'},
            {'product': self.soap.pk, 'quantity': '6'},
        ])
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Sale.objects.count(), 0)
        self.sugar.refresh_from_db()
        self.assertEqual(self.sugar.stock_quantity, 10)

    def test_same_product_twice_checks_combined_quantity(self):
        response = self.sell([
            {'product': self.soap.pk, 'quantity': '3'},
            {'product': self.soap.pk, 'quantity': '3'},
        ])
        self.assertEqual(response.status_code, 400)

    def test_list_includes_total_of_all_matching_sales(self):
        self.sell([{'product': self.sugar.pk, 'quantity': '2'}])
        self.sell([{'product': self.soap.pk, 'quantity': '1'}], payment_method='cash')
        response = self.client.get('/api/sales/?period=today&page_size=1')
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['total'], Decimal('7900'))

    def test_list_is_newest_first(self):
        # Record the older sale last, so database insert order differs from sale time order
        self.sell([{'product': self.sugar.pk, 'quantity': '1'}], sold_at='2026-10-20T10:00:00+03:00')
        self.sell([{'product': self.sugar.pk, 'quantity': '1'}], sold_at='2026-10-22T10:00:00+03:00')
        self.sell([{'product': self.sugar.pk, 'quantity': '1'}], sold_at='2026-10-18T10:00:00+03:00')
        receipts = [s['receipt_number'] for s in self.client.get('/api/sales/').data['results']]
        self.assertEqual(receipts, ['R00002', 'R00001', 'R00003'])

    def test_receipt_numbers_increase(self):
        self.sell([{'product': self.sugar.pk, 'quantity': '1'}])
        response = self.sell([{'product': self.sugar.pk, 'quantity': '1'}])
        self.assertEqual(response.data['receipt_number'], 'R00002')

    def test_profit_uses_cost_at_time_of_sale(self):
        sale_id = self.sell([{'product': self.sugar.pk, 'quantity': '1'}]).data['id']
        self.sugar.cost_price = 3000
        self.sugar.save()
        sale = self.client.get(f'/api/sales/{sale_id}/').data
        self.assertEqual(Decimal(sale['profit']), 400)

    def test_cancel_sale_returns_stock(self):
        sale_id = self.sell([{'product': self.sugar.pk, 'quantity': '3'}]).data['id']
        self.assertEqual(self.client.delete(f'/api/sales/{sale_id}/').status_code, 204)
        self.sugar.refresh_from_db()
        self.assertEqual(self.sugar.stock_quantity, 10)

    def test_staff_can_sell_but_not_cancel(self):
        staff = User.objects.create_user(
            phone='+255655000111', password='x', business=self.business, role=User.Role.STAFF
        )
        staff_client = client_for(staff)
        response = staff_client.post(
            '/api/sales/', {'items': [{'product': self.sugar.pk, 'quantity': '1'}]}, format='json'
        )
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(staff_client.delete(f"/api/sales/{response.data['id']}/").status_code, 403)

    def test_cannot_sell_other_business_product(self):
        other_business, _ = make_business('Duka B', '+255712000002')
        other_product = Product.objects.create(
            business=other_business, name='Nje', cost_price=1, selling_price=2, stock_quantity=5
        )
        response = self.sell([{'product': other_product.pk, 'quantity': '1'}])
        self.assertEqual(response.status_code, 400)
