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


class OfflineSaleTests(TestCase):
    """Sales recorded on a phone without internet and sent later."""

    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)
        self.sugar = Product.objects.create(
            business=self.business, name='Sukari 1kg', cost_price=2800, selling_price=3200, stock_quantity=1
        )

    def send(self, client_id='5b0c6c1e-8d1f-4a52-9a40-1b2c3d4e5f60', quantity='1', **extra):
        return self.client.post('/api/sales/', {
            'items': [{'product': self.sugar.pk, 'quantity': quantity, 'unit_price': '3200'}],
            'payment_method': 'cash', 'client_id': client_id, 'recorded_offline': True, **extra,
        }, format='json')

    def test_same_sale_sent_twice_is_saved_once(self):
        first = self.send()
        second = self.send()
        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data['id'], second.data['id'])
        self.assertEqual(Sale.objects.count(), 1)
        self.sugar.refresh_from_db()
        self.assertEqual(self.sugar.stock_quantity, 0)

    def test_offline_sale_is_kept_when_stock_runs_out(self):
        response = self.send(quantity='3')
        self.assertEqual(response.status_code, 201, response.data)
        self.assertTrue(response.data['recorded_offline'])
        self.sugar.refresh_from_db()
        self.assertEqual(self.sugar.stock_quantity, -2)

    def test_online_sale_still_needs_enough_stock(self):
        response = self.client.post('/api/sales/', {
            'items': [{'product': self.sugar.pk, 'quantity': '3'}], 'payment_method': 'cash',
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_sale_keeps_the_time_it_happened(self):
        response = self.send(sold_at='2026-10-20T09:30:00+03:00')
        self.assertEqual(Sale.objects.get(pk=response.data['id']).sold_at.isoformat(), '2026-10-20T06:30:00+00:00')

    def test_future_time_from_a_wrong_clock_becomes_now(self):
        response = self.send(sold_at='2099-01-01T00:00:00Z')
        self.assertLess(Sale.objects.get(pk=response.data['id']).sold_at.year, 2099)

    def test_client_ids_are_per_business(self):
        self.send()
        other_business, other_owner = make_business(name='Duka B', phone='0712000009')
        tea = Product.objects.create(business=other_business, name='Chai', cost_price=1, selling_price=2, stock_quantity=5)
        response = client_for(other_owner).post('/api/sales/', {
            'items': [{'product': tea.pk, 'quantity': '1'}], 'payment_method': 'cash',
            'client_id': '5b0c6c1e-8d1f-4a52-9a40-1b2c3d4e5f60',
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Sale.objects.count(), 2)
