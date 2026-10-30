from django.test import TestCase
from rest_framework.authtoken.models import Token
from rest_framework.test import APIClient

from .models import Client, CustomUser


class SignupTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.payload = {
            'user_type': 'client',
            'user': {
                'username': 'farmer',
                'email': 'farmer@example.com',
                'password': 'S3cure-pass!',
                'first_name': 'Ali',
                'last_name': 'B',
            },
        }

    def test_signup_creates_client_with_hashed_password(self):
        response = self.client.post('/user_management/signup', self.payload, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertNotIn('password', response.data)
        user = CustomUser.objects.get(username='farmer')
        self.assertTrue(user.check_password('S3cure-pass!'))
        self.assertNotEqual(user.password, 'S3cure-pass!')
        self.assertTrue(Client.objects.filter(user=user).exists())

    def test_signup_rejects_invalid_user_type(self):
        self.payload['user_type'] = 'hacker'
        response = self.client.post('/user_management/signup', self.payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertFalse(CustomUser.objects.exists())

    def test_signup_rejects_duplicate_email(self):
        self.client.post('/user_management/signup', self.payload, format='json')
        self.payload['user']['username'] = 'other'
        response = self.client.post('/user_management/signup', self.payload, format='json')

        self.assertEqual(response.status_code, 400)
        self.assertIn('email', response.data)


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='farmer', email='farmer@example.com', password='S3cure-pass!'
        )

    def test_login_returns_token_and_user(self):
        response = self.client.post(
            '/user_management/login', {'username': 'farmer', 'password': 'S3cure-pass!'}, format='json'
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['token'], Token.objects.get(user=self.user).key)
        self.assertEqual(response.data['user']['username'], 'farmer')

    def test_login_wrong_password(self):
        response = self.client.post(
            '/user_management/login', {'username': 'farmer', 'password': 'wrong'}, format='json'
        )
        self.assertEqual(response.status_code, 401)

    def test_login_unknown_user(self):
        response = self.client.post(
            '/user_management/login', {'username': 'nobody', 'password': 'x'}, format='json'
        )
        self.assertEqual(response.status_code, 401)

    def test_login_missing_fields(self):
        response = self.client.post('/user_management/login', {'username': 'farmer'}, format='json')
        self.assertEqual(response.status_code, 400)

    def test_get_user_info_requires_token(self):
        response = self.client.get('/user_management/get_user_info/')
        self.assertEqual(response.status_code, 401)

    def test_get_user_info_with_token(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.get('/user_management/get_user_info/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['email'], 'farmer@example.com')

    def test_logout_revokes_token(self):
        token = Token.objects.create(user=self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.post('/user_management/logout')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Token.objects.filter(user=self.user).exists())
