from django.test import TestCase


class PublicPagesTests(TestCase):
    """Opening the backend in a browser should show helpful pages, not errors."""

    def test_home_page(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SAVIOR API')
        self.assertContains(response, 'href="http://localhost:5173"')

    def test_api_index_is_public_but_data_is_not(self):
        index = self.client.get('/api/', HTTP_ACCEPT='application/json')
        self.assertEqual(index.status_code, 200)
        self.assertIn('products', index.json())
        self.assertEqual(self.client.get('/api/products/').status_code, 401)
