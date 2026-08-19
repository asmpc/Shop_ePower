from django.urls import reverse

from rest_framework import status
from rest_framework.test import APITestCase
from shop_epower.accounts.models import LegalProfile
from shop_epower.accounts.tests.helpers import create_test_user



class TestsProfileApi(APITestCase):

    def setUp(self):
        self.user = create_test_user(
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
