from django.test import TestCase

from django.contrib.auth import get_user_model


from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode
from django.utils.encoding import force_bytes
from django.urls import reverse


User = get_user_model()


class TestsFrontendAuth(TestCase):

    # Подготавливаем тестового пользователя,
    # который будет использоваться для login/logout/profile/password reset тестов.
    def setUp(self):

        self.user = User.objects.create_user(
            email='test@test.com',
            username='testuser',
            password='strongpassword123'
        )

    # Проверяем, что страница логина открывается
    # и возвращает HTTP 200.
    def test_login_page_open(self):

        response = self.client.get(
            reverse('accounts:login'),

        )

        self.assertEqual(
            response.status_code,
            200
        )

    # Проверяем, что страница регистрации открывается
    # и возвращает HTTP 200.
    def test_register_page_open(self):

        response = self.client.get(
            reverse('accounts:register'),
        )

        self.assertEqual(
            response.status_code,
            200
        )

    # Проверяем, что пользователь может авторизоваться
    # через frontend login form.
    def test_user_can_login(self):

        response = self.client.post(
            reverse('accounts:login'),
            {
                'username': 'test@test.com',
                'password': 'strongpassword123',
            },
            follow=True
        )

        self.assertTrue(
            response.context['user'].is_authenticated
        )

    # Проверяем, что авторизованный пользователь может выйти из аккаунта
    # через frontend logout view.
    def test_user_can_logout(self):

        self.client.login(
            username='test@test.com',
            password='strongpassword123'
        )

        response = self.client.post(
            reverse('accounts:logout'),
            follow=True
        )

        self.assertFalse(
            response.context['user'].is_authenticated
        )

    # Проверяем, что страница профиля защищена авторизацией:
    # неавторизованный пользователь получает redirect на login.
    def test_profile_requires_auth(self):

        response = self.client.get(
            reverse('accounts:profile')
        )

        self.assertEqual(
            response.status_code,
            302
        )

        self.assertIn(
            reverse('accounts:login'),
            response.url
        )

    # Проверяем, что авторизованный пользователь может открыть страницу профиля.
    def test_authenticated_user_can_open_profile(self):

        self.client.login(
            username='test@test.com',
            password='strongpassword123'
        )

        response = self.client.get(
            reverse('accounts:profile')
        )

        self.assertEqual(
            response.status_code,
            200
        )

    # Проверяем core-логику перехода по ссылке сброса пароля:
    # генерируем uid и token вручную, затем открываем password_reset_confirm.
    # Здесь не тестируем отправку email, а только валидность reset-ссылки.
    def test_user_can_reset_password(self):
        user = self.user  # или создавай нового

        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = default_token_generator.make_token(user)

        reset_url = reverse(
            'accounts:password_reset_confirm',
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