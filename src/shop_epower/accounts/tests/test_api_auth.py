from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APITestCase


User = get_user_model()

class TestsAuthApi(APITestCase):

    def test_register_user(self):

        data = {
            'email': 'test@test.com',
            'username': 'test',
            'password': '12345678',
        }

        response = self.client.post(
            reverse('api-register'),
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_201_CREATED
        )

        self.assertEqual(
            User.objects.count(),
            1
        )

        self.assertEqual(
            User.objects.first().email,
            'test@test.com'
        )

    def test_user_login(self):
        User.objects.create_user(
            email='test@test.com',
            username='test',
            password='12345678'
        )

        data = {
            'email': 'test@test.com',
            'password': '12345678',
        }

        response = self.client.post(
            reverse('api-login'),
            data
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertIn('access', response.data)

        self.assertIn('refresh', response.data)

    def test_token_refresh(self):
        user = User.objects.create_user(
            email='test@test.com',
            username='test',
            password='12345678'
        )

        login_response = self.client.post(
            reverse('api-login'),
            {
                'email': 'test@test.com',
                'password': '12345678',
            }
        )

        refresh_token = login_response.data['refresh']

        response = self.client.post(
            reverse('api-refresh'),
            {
                'refresh': refresh_token
            }
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertIn('access', response.data)

    def test_user_logout(self):
        User.objects.create_user(
            email='test@test.com',
            username='test',
            password='12345678'
        )

        login_response = self.client.post(
            reverse('api-login'),
            {
                'email': 'test@test.com',
                'password': '12345678',
            }
        )

        access_token = login_response.data['access']

        refresh_token = login_response.data['refresh']

        self.client.credentials(
            HTTP_AUTHORIZATION=f'JWT {access_token}'
        )

        response = self.client.post(
            reverse('api-logout'),
            {
                'refresh': refresh_token
            }
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_205_RESET_CONTENT
        )

    def test_blacklisted_token_cannot_refresh(self):
        User.objects.create_user(
            email='test@test.com',
            username='test',
            password='12345678'
        )

        login_response = self.client.post(
            reverse('api-login'),
            {
                'email': 'test@test.com',
                'password': '12345678',
            }
        )

        access_token = login_response.data['access']

        refresh_token = login_response.data['refresh']

        self.client.credentials(
            HTTP_AUTHORIZATION=f'JWT {access_token}'
        )

        self.client.post(
            reverse('api-logout'),
            {
                'refresh': refresh_token
            }
        )

        refresh_response = self.client.post(
            reverse('api-refresh'),
            {
                'refresh': refresh_token
            }
        )

        self.assertEqual(
            refresh_response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )
