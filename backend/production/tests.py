from decimal import Decimal

from django.test import TestCase

from accounts.models import User
from accounts.testing import client_for, make_business
from inventory.models import Product, StockMovement

from .models import ProductionRun


class ProductionTests(TestCase):
    """A bakery: bread is made from flour and sugar."""

    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)
        self.flour = Product.objects.create(
            business=self.business, name='Unga', unit='kg', cost_price=2000, selling_price=0,
            stock_quantity=25, is_material=True,
        )
        self.sugar = Product.objects.create(
            business=self.business, name='Sukari', unit='kg', cost_price=3000, selling_price=0,
            stock_quantity=5, is_material=True,
        )
        self.bread = Product.objects.create(
            business=self.business, name='Mkate', cost_price=0, selling_price=1000, stock_quantity=0
        )

    def produce(self, quantity='50', flour='10', sugar='1', **extra):
        return self.client.post('/api/production/', {
            'product': self.bread.pk, 'quantity': quantity,
            'items': [{'material': self.flour.pk, 'quantity': flour}, {'material': self.sugar.pk, 'quantity': sugar}],
            **extra,
        }, format='json')

    def stock(self, product):
        product.refresh_from_db()
        return product.stock_quantity

    def test_production_moves_stock_and_calculates_cost(self):
        response = self.produce(extra_cost='2000')
        self.assertEqual(response.status_code, 201, response.data)
        # 10 kg x 2,000 + 1 kg x 3,000 = 23,000 materials + 2,000 charcoal = 25,000 for 50 loaves
        self.assertEqual(Decimal(response.data['materials_cost']), 23000)
        self.assertEqual(Decimal(response.data['total_cost']), 25000)
        self.assertEqual(Decimal(response.data['unit_cost']), 500)
        self.assertEqual(response.data['batch_number'], 'P00001')

        self.assertEqual(self.stock(self.flour), 15)
        self.assertEqual(self.stock(self.sugar), 4)
        self.assertEqual(self.stock(self.bread), 50)
        self.assertEqual(self.bread.cost_price, 500)
        types = set(StockMovement.objects.values_list('movement_type', flat=True))
        self.assertEqual(types, {'used_in_production', 'produced'})

    def test_cost_price_is_averaged_with_existing_stock(self):
        self.produce(extra_cost='2000')  # 50 loaves at 500
        self.flour.cost_price = 2500  # flour got more expensive
        self.flour.save()
        self.produce(extra_cost='2000')  # 10 x 2,500 + 3,000 + 2,000 = 30,000 -> 600 each
        self.bread.refresh_from_db()
        self.assertEqual(self.bread.cost_price, 550)  # (50 x 500 + 50 x 600) / 100

    def test_profit_on_sales_uses_production_cost(self):
        self.produce(extra_cost='2000')
        sale = self.client.post('/api/sales/', {
            'items': [{'product': self.bread.pk, 'quantity': '10'}], 'payment_method': 'cash',
        }, format='json')
        self.assertEqual(Decimal(sale.data['profit']), 5000)  # 10 x (1,000 - 500)

    def test_not_enough_material_is_refused(self):
        response = self.produce(sugar='6')
        self.assertEqual(response.status_code, 400)
        self.assertIn('Sukari', str(response.data))
        self.assertEqual(self.stock(self.flour), 25)  # nothing changed
        self.assertFalse(ProductionRun.objects.exists())

    def test_product_cannot_be_made_from_itself(self):
        response = self.client.post('/api/production/', {
            'product': self.bread.pk, 'quantity': '1', 'items': [{'material': self.bread.pk, 'quantity': '1'}],
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_cancel_puts_stock_back(self):
        run_id = self.produce().data['id']
        self.assertEqual(self.client.delete(f'/api/production/{run_id}/').status_code, 204)
        self.assertEqual((self.stock(self.flour), self.stock(self.sugar), self.stock(self.bread)), (25, 5, 0))

    def test_cannot_cancel_after_products_were_sold(self):
        run_id = self.produce().data['id']
        self.client.post('/api/sales/', {
            'items': [{'product': self.bread.pk, 'quantity': '5'}], 'payment_method': 'cash',
        }, format='json')
        response = self.client.delete(f'/api/production/{run_id}/')
        self.assertEqual(response.status_code, 400)
        self.assertEqual(self.stock(self.bread), 45)

    def test_staff_can_record_but_not_cancel(self):
        staff = User.objects.create_user(
            phone='0712000002', password='siri-kali-123', first_name='Neema', business=self.business, role='staff'
        )
        staff_client = client_for(staff)
        response = staff_client.post('/api/production/', {
            'product': self.bread.pk, 'quantity': '10', 'items': [{'material': self.flour.pk, 'quantity': '2'}],
        }, format='json')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(staff_client.delete(f'/api/production/{response.data["id"]}/').status_code, 403)

    def test_list_shows_total_cost(self):
        self.produce(extra_cost='2000')
        data = self.client.get('/api/production/', {'period': 'month'}).data
        self.assertEqual(len(data['results']), 1)
        self.assertEqual(Decimal(data['total']), 25000)

    def test_materials_are_not_sold_or_shown_at_the_till(self):
        sale = self.client.post('/api/sales/', {
            'items': [{'product': self.flour.pk, 'quantity': '1'}], 'payment_method': 'cash',
        }, format='json')
        self.assertEqual(sale.status_code, 400)
        names = [p['name'] for p in self.client.get('/api/products/', {'kind': 'goods'}).data['results']]
        self.assertEqual(names, ['Mkate'])
        names = [p['name'] for p in self.client.get('/api/products/', {'kind': 'material'}).data['results']]
        self.assertEqual(names, ['Sukari', 'Unga'])


class RecipeTests(TestCase):
    def setUp(self):
        self.business, self.owner = make_business()
        self.client = client_for(self.owner)
        self.flour = Product.objects.create(
            business=self.business, name='Unga', cost_price=2000, selling_price=0, is_material=True
        )
        self.bread = Product.objects.create(business=self.business, name='Mkate', cost_price=0, selling_price=1000)

    def save_recipe(self, **overrides):
        body = {'product': self.bread.pk, 'output_quantity': '50', 'items': [{'material': self.flour.pk, 'quantity': '10'}]}
        return self.client.post('/api/recipes/', {**body, **overrides}, format='json')

    def test_recipe_shows_cost_per_item(self):
        response = self.save_recipe()
        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(Decimal(response.data['cost_per_batch']), 20000)
        self.assertEqual(Decimal(response.data['cost_per_unit']), 400)

    def test_one_recipe_per_product(self):
        self.save_recipe()
        self.assertEqual(self.save_recipe().status_code, 400)

    def test_edit_replaces_materials(self):
        recipe_id = self.save_recipe().data['id']
        sugar = Product.objects.create(business=self.business, name='Sukari', cost_price=3000, selling_price=0)
        response = self.client.patch(f'/api/recipes/{recipe_id}/', {
            'items': [{'material': sugar.pk, 'quantity': '2'}],
        }, format='json')
        self.assertEqual([i['material_name'] for i in response.data['items']], ['Sukari'])

    def test_invalid_recipes_are_refused(self):
        self.assertEqual(self.save_recipe(items=[]).status_code, 400)
        self.assertEqual(self.save_recipe(items=[{'material': self.bread.pk, 'quantity': '1'}]).status_code, 400)
        twice = [{'material': self.flour.pk, 'quantity': '1'}, {'material': self.flour.pk, 'quantity': '2'}]
        self.assertEqual(self.save_recipe(items=twice).status_code, 400)

    def test_other_shops_materials_cannot_be_used(self):
        other, _ = make_business(name='Duka B', phone='0712000009')
        theirs = Product.objects.create(business=other, name='Unga B', cost_price=1, selling_price=0)
        self.assertEqual(self.save_recipe(items=[{'material': theirs.pk, 'quantity': '1'}]).status_code, 400)
