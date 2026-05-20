from django.test import TestCase
from django.urls import reverse

from django.contrib.auth import get_user_model


from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse


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


    '''
    тест на сброс пароля по ссылке, проблема в том, что получаемая ссылка имеет = 
    если из ссылки удалить = то переход на форму смены пароля осуществляется.
    в тесте не тестирую email, а тестирую внутреннюю Core логику (uid + token + проверка)
     '''
    def test_user_can_reset_password(self):
        user = self.user  # или создавай нового

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_url = reverse(
            'password_reset_confirm',
            kwargs={
                'uidb64': uid,
                'token': token
            }
        )

        response = self.client.get(reset_url)

        # иногда Django делает redirect -> follow=True
        self.assertEqual(
            response.status_code in [200, 302],
            True
        )

        response = self.client.get(reset_url, follow=True)

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            'Set new password'
        )