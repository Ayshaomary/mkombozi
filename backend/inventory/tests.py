from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from accounts.testing import client_for, make_business

from .models import Product, StockMovement


class ProductTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)

    def create_product(self, **overrides):
        data = {'name': 'Sukari 1kg', 'cost_price': '2800', 'selling_price': '3200', 'opening_stock': '20', **overrides}
        return self.client.post('/api/products/', data, format='json')

    def test_create_product_with_opening_stock_records_movement(self):
        response = self.create_product()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data['stock_quantity']), 20)
        movement = StockMovement.objects.get(product_id=response.data['id'])
        self.assertEqual(movement.movement_type, StockMovement.Type.OPENING)

    def test_stock_cannot_be_edited_directly(self):
        product_id = self.create_product().data['id']
        self.client.patch(f'/api/products/{product_id}/', {'stock_quantity': '999'}, format='json')
        self.assertEqual(Product.objects.get(pk=product_id).stock_quantity, 20)

    def test_purchase_and_adjustment(self):
        product_id = self.create_product().data['id']
        url = f'/api/products/{product_id}/stock/'
        response = self.client.post(url, {'movement_type': 'purchase', 'quantity': '10', 'new_cost_price': '2900'}, format='json')
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Decimal(response.data['stock_quantity']), 30)
        self.assertEqual(Decimal(response.data['cost_price']), 2900)

        response = self.client.post(url, {'movement_type': 'adjustment', 'quantity': '-2', 'note': 'Imeharibika'}, format='json')
        self.assertEqual(Decimal(response.data['stock_quantity']), 28)

    def test_stock_cannot_go_negative(self):
        product_id = self.create_product().data['id']
        response = self.client.post(
            f'/api/products/{product_id}/stock/', {'movement_type': 'adjustment', 'quantity': '-50'}, format='json'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(Product.objects.get(pk=product_id).stock_quantity, 20)

    def test_categories_are_alphabetical(self):
        for name in ['Vyakula', 'Usafi', 'Vinywaji']:
            self.client.post('/api/categories/', {'name': name})
        names = [c['name'] for c in self.client.get('/api/categories/').data]
        self.assertEqual(names, ['Usafi', 'Vinywaji', 'Vyakula'])

    def test_low_stock_filter(self):
        self.create_product(name='Chumvi', opening_stock='2')
        self.create_product(name='Mchele', opening_stock='100')
        response = self.client.get('/api/products/?low_stock=true')
        self.assertEqual([p['name'] for p in response.data['results']], ['Chumvi'])

    def test_staff_can_view_but_not_create(self):
        _, staff = make_business(name='ignored', phone='+255712000099')
        staff.business, staff.role = self.business, User.Role.STAFF
        staff.save()
        staff_client = client_for(staff)
        self.assertEqual(staff_client.get('/api/products/').status_code, 200)
        self.assertEqual(staff_client.post('/api/products/', {'name': 'X', 'cost_price': 1, 'selling_price': 2}).status_code, 403)


class BusinessIsolationTests(TestCase):
    """One business must never see or touch another business's data."""

    def test_other_business_products_are_invisible(self):
        business_a, owner_a = make_business('Duka A', '+255712000001')
        business_b, owner_b = make_business('Duka B', '+255712000002')
        product_b = Product.objects.create(business=business_b, name='Siri ya B', cost_price=1, selling_price=2)

        client_a = client_for(owner_a)
        self.assertEqual(client_a.get('/api/products/').data['count'], 0)
        self.assertEqual(client_a.get(f'/api/products/{product_b.pk}/').status_code, 404)
        self.assertEqual(client_a.delete(f'/api/products/{product_b.pk}/').status_code, 404)

    def test_cannot_use_other_business_category(self):
        _, owner_a = make_business('Duka A', '+255712000001')
        _, owner_b = make_business('Duka B', '+255712000002')
        category_b = client_for(owner_b).post('/api/categories/', {'name': 'Vinywaji'}).data['id']
        response = client_for(owner_a).post(
            '/api/products/', {'name': 'Soda', 'cost_price': 500, 'selling_price': 700, 'category': category_b}
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn('category', response.data)
