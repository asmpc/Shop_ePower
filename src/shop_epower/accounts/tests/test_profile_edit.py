from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model

from shop_epower.accounts.models import LegalProfile


User = get_user_model()


class ProfileEditViewTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            email='user@test.com',
            username='user',
            password='strongpassword123',
        )

        self.url = reverse('accounts:profile_edit')

    # Проверяем, что страница редактирования профиля
    # доступна только авторизованному пользователю.
    def test_profile_edit_requires_login(self):

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('accounts:login'), response.url)

    # Проверяем, что при первом заходе создаётся LegalProfile.
    def test_profile_edit_get_creates_legal_profile(self):

        self.client.login(
            email='user@test.com',
            password='strongpassword123',
        )

        self.assertFalse(
            LegalProfile.objects.filter(user=self.user).exists()
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        self.assertTrue(
            LegalProfile.objects.filter(user=self.user).exists()
        )

    # Проверяем, что пользователь может обновить свои данные.
    def test_profile_edit_post_updates_user(self):

        self.client.login(
            email='user@test.com',
            password='strongpassword123',
        )

        response = self.client.post(
            self.url,
            data={
                'username': 'new_username',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'new@test.com',
                'phone': '+123456789',

                'is_legal_entity': False,
            },
        )

        self.assertEqual(response.status_code, 302)

        self.user.refresh_from_db()

        self.assertEqual(self.user.username, 'new_username')
        self.assertEqual(self.user.first_name, 'John')
        self.assertEqual(self.user.last_name, 'Doe')
        self.assertEqual(self.user.email, 'new@test.com')
        self.assertEqual(self.user.phone, '+123456789')

    # Проверяем, что при включённом чекбоксе
    # юр. поля обязательны.
    def test_profile_edit_requires_legal_fields_when_enabled(self):

        self.client.login(
            email='user@test.com',
            password='strongpassword123',
        )

        response = self.client.post(
            self.url,
            data={
                'username': 'user',
                'email': 'user@test.com',

                'is_legal_entity': True,
            },
        )

        self.assertEqual(response.status_code, 200)

        form = response.context['legal_profile_form']

        self.assertTrue(form.errors)
        self.assertIn('company_name', form.errors)

    # Проверяем, что при включённом чекбоксе
    # данные юрлица сохраняются.
    def test_profile_edit_saves_legal_profile(self):

        self.client.login(
            email='user@test.com',
            password='strongpassword123',
        )

        response = self.client.post(
            self.url,
            data={
                'username': 'user',
                'email': 'user@test.com',

                'is_legal_entity': True,
                'company_name': 'Test Company',
                'tax_id': '123456789',
                'legal_address': 'Minsk',
                'bank_name': 'Test Bank',
                'bank_account': 'BY00TEST123456',
            },
        )

        self.assertEqual(response.status_code, 302)

        legal_profile = LegalProfile.objects.get(user=self.user)

        self.assertTrue(legal_profile.is_legal_entity)
        self.assertEqual(legal_profile.company_name, 'Test Company')

    # Проверяем, что данные НЕ удаляются,
    # если пользователь снимает чекбокс.
    def test_profile_edit_keeps_legal_data_when_disabled(self):

        self.client.login(
            email='user@test.com',
            password='strongpassword123',
        )

        legal_profile = LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=True,
            company_name='Old Company',
            tax_id='123',
        )

        response = self.client.post(
            self.url,
            data={
                'username': 'user',
                'email': 'user@test.com',

                'is_legal_entity': False,
            },
        )

        self.assertEqual(response.status_code, 302)

        legal_profile.refresh_from_db()

        self.assertFalse(legal_profile.is_legal_entity)
        self.assertEqual(legal_profile.company_name, 'Old Company')