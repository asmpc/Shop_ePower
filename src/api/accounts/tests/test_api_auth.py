from django.urls import reverse
from django.contrib.auth import get_user_model

from rest_framework import status
from rest_framework.test import APITestCase
from shop_epower.accounts.models import LegalProfile


User = get_user_model()

class TestsAuthApi(APITestCase):

    # Проверяем API-регистрацию пользователя:
    # endpoint должен создать нового пользователя и вернуть HTTP 201.
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

    # Проверяем API-логин:
    # при правильных данных endpoint должен вернуть access и refresh JWT tokens.
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

    # Проверяем обновление access token через refresh token.
    # При валидном refresh token API должен вернуть новый access token.
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

    # Проверяем API-logout:
    # авторизованный пользователь отправляет refresh token,
    # после чего endpoint должен вернуть HTTP 205.
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

    # Проверяем blacklist-логику:
    # после logout refresh token попадает в blacklist
    # и больше не может использоваться для получения нового access token.
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

    # Проверяем, что login с неправильным паролем не возвращает токены.
    def test_user_login_with_invalid_password_fails(self):
        User.objects.create_user(
            email='test@test.com',
            username='test',
            password='12345678'
        )

        response = self.client.post(
            reverse('api-login'),
            {
                'email': 'test@test.com',
                'password': 'wrong-password',
            }
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

        self.assertNotIn('access', response.data)
        self.assertNotIn('refresh', response.data)


class TestsProfileApi(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='user@test.com',
            username='user',
            password='12345678',
        )

        self.url = reverse('api-profile')

    # Проверяем, что профиль доступен только авторизованному пользователю.
    def test_profile_requires_auth(self):

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_401_UNAUTHORIZED
        )

    # Проверяем получение профиля текущего пользователя.
    def test_user_can_get_profile(self):

        self.client.force_authenticate(user=self.user)

        response = self.client.get(self.url)

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.assertEqual(
            response.data['email'],
            'user@test.com'
        )

        self.assertIn(
            'legal_profile',
            response.data
        )

    # Проверяем обновление основных данных пользователя.
    def test_user_can_update_profile(self):

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                'first_name': 'John',
                'last_name': 'Doe',
                'phone': '+123456789',
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        self.user.refresh_from_db()

        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')
        self.assertEqual(self.user.phone, '+123456789')

    # Проверяем сохранение данных юрлица / ИП.
    def test_user_can_update_legal_profile(self):

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                'legal_profile': {
                    'is_legal_entity': True,
                    'company_name': 'Test Company',
                    'tax_id': '123456789',
                    'legal_address': 'Minsk',
                    'bank_name': 'Test Bank',
                    'bank_account': 'BY00TEST123456',
                }
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        legal_profile = LegalProfile.objects.get(user=self.user)

        self.assertTrue(legal_profile.is_legal_entity)
        self.assertEqual(legal_profile.company_name, 'Test Company')
        self.assertEqual(legal_profile.tax_id, '123456789')

    # Проверяем, что при включённом юрлице обязательные поля валидируются.
    def test_legal_profile_requires_fields_when_enabled(self):

        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            self.url,
            {
                'legal_profile': {
                    'is_legal_entity': True,
                }
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_400_BAD_REQUEST
        )

        self.assertIn(
            'company_name',
            response.data['legal_profile']
        )

    # Проверяем, что при выключении юрлица данные не удаляются.
    def test_legal_profile_data_kept_when_disabled(self):

        self.client.force_authenticate(user=self.user)

        LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=True,
            company_name='Old Company',
            tax_id='123456789',
            legal_address='Old Address',
            bank_name='Old Bank',
            bank_account='Old Account',
        )

        response = self.client.patch(
            self.url,
            {
                'legal_profile': {
                    'is_legal_entity': False,
                }
            },
            format='json',
        )

        self.assertEqual(
            response.status_code,
            status.HTTP_200_OK
        )

        legal_profile = LegalProfile.objects.get(user=self.user)

        self.assertFalse(legal_profile.is_legal_entity)
        self.assertEqual(legal_profile.company_name, 'Old Company')
        self.assertEqual(legal_profile.tax_id, '123456789')
