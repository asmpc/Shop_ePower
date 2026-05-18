from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model


User = get_user_model()


class TestsFrontendAuth(TestCase):

    def setUp(self):

        self.user = User.objects.create_user(
            email='test@test.com',
            username='testuser',
            password='strongpassword123'
        )

    def test_login_page_open(self):

        response = self.client.get(
            reverse('login-template')
        )

        self.assertEqual(
            response.status_code,
            200
        )

    def test_register_page_open(self):

        response = self.client.get(
            reverse('register-template')
        )

        self.assertEqual(
            response.status_code,
            200
        )

    def test_user_can_login(self):

        response = self.client.post(
            reverse('login-template'),
            {
                'username': 'test@test.com',
                'password': 'strongpassword123',
            },
            follow=True
        )

        self.assertTrue(
            response.context['user'].is_authenticated
        )

    def test_user_can_logout(self):

        self.client.login(
            username='test@test.com',
            password='strongpassword123'
        )

        response = self.client.post(
            reverse('logout-template'),
            follow=True
        )

        self.assertFalse(
            response.context['user'].is_authenticated
        )

    def test_profile_requires_auth(self):

        response = self.client.get(
            reverse('profile')
        )

        self.assertEqual(
            response.status_code,
            302
        )

    def test_authenticated_user_can_open_profile(self):

        self.client.login(
            username='test@test.com',
            password='strongpassword123'
        )

        response = self.client.get(
            reverse('profile')
        )

        self.assertEqual(
            response.status_code,
            200
        )