from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


User = get_user_model()


class TestsRegisterView(TestCase):

    def setUp(self):

        self.url = reverse('accounts:register')

        self.data = {
            'email': 'newuser@test.com',
            'username': 'newuser',
            'password1': 'strongpassword123',
            'password2': 'strongpassword123',
        }

    # Проверяем, что после успешной регистрации
    # пользователь авторизуется и перенаправляется на заполнение профиля.
    def test_successful_registration_redirects_to_profile_edit(self):

        response = self.client.post(
            self.url,
            data=self.data,
        )

        self.assertRedirects(
            response,
            reverse('accounts:profile_edit'),
            fetch_redirect_response=False,
        )

        user = User.objects.get(
            email='newuser@test.com',
        )

        self.assertEqual(
            int(self.client.session['_auth_user_id']),
            user.pk,
        )

    # Проверяем, что при невалидной регистрации
    # пользователь не создаётся и не авторизуется.
    def test_invalid_registration_does_not_authenticate_user(self):

        invalid_data = self.data.copy()
        invalid_data['password2'] = 'differentpassword123'

        response = self.client.post(
            self.url,
            data=invalid_data,
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertFalse(
            User.objects.filter(
                email='newuser@test.com',
            ).exists()
        )

        self.assertNotIn(
            '_auth_user_id',
            self.client.session,
        )