from django.test import TestCase


class LegalPagesTests(TestCase):
    def test_public_pages_render(self):
        for url in ['/app-info/', '/privacy-policy/', '/terms/', '/account-deletion/']:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.content)
