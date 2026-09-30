from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.models import LegalProfile
from shop_epower.accounts.tests.helpers import (
    create_test_legal_profile,
    create_test_user,
)
from shop_epower.finance.models import (
    AccountTransactionActorType,
    CustomerAccount,
    CustomerAccountType,
)
from shop_epower.finance.services import (
    create_legal_customer_account,
    record_customer_deposit,
)


class TestsProfileEditView(TestCase):

    def setUp(self):
        self.user = create_test_user(
            email="user@test.com",
            username="user",
            password="strongpassword123",
            first_name="",
            last_name="",
            phone="",
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
        self.assertEqual(
            CustomerAccount.objects.filter(
                user=self.user,
                account_type=CustomerAccountType.LEGAL,
                legal_profile=legal_profile,
            ).count(),
            1,
        )

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

    # Проверяем, что после успешного сохранения профиля
    # пользователь возвращается на страницу из параметра next.
    def test_profile_edit_redirects_to_next_url(self):

        self.client.login(
            email='user@test.com',
            password='strongpassword123',
        )

        cart_url = reverse(
            'cart-detail',
        )

        response = self.client.post(
            f'{self.url}?next={cart_url}',
            data={
                'username': 'user',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'user@test.com',
                'phone': '+123456789',

                'is_legal_entity': False,
            },
        )

        self.assertRedirects(
            response,
            cart_url,
        )

    # Проверяем, что внешний next игнорируется
    # и пользователь остаётся на странице профиля.
    def test_profile_edit_ignores_external_next_url(self):

        self.client.login(
            email='user@test.com',
            password='strongpassword123',
        )

        response = self.client.post(
            f'{self.url}?next=https://evil.example',
            data={
                'username': 'user',
                'first_name': 'John',
                'last_name': 'Doe',
                'email': 'user@test.com',
                'phone': '+123456789',

                'is_legal_entity': False,
            },
        )

        self.assertRedirects(
            response,
            reverse('accounts:profile_edit'),
        )

    # После финансовой операции УНП нельзя изменить через страницу профиля.
    def test_profile_edit_rejects_tax_id_change_after_financial_activity(self):
        profile = create_test_legal_profile(user=self.user)
        account = create_legal_customer_account(legal_profile=profile)

        record_customer_deposit(
            account=account,
            amount=Decimal("10.00"),
            operation_key="profile:legal-tax-change:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        self.client.force_login(self.user)

        response = self.client.post(
            self.url,
            data={
                "username": self.user.username,
                "email": self.user.email,
                "is_legal_entity": True,
                "company_name": profile.company_name,
                "tax_id": "987654321",
                "legal_address": profile.legal_address,
                "bank_name": profile.bank_name,
                "bank_account": profile.bank_account,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("tax_id", response.context["legal_profile_form"].errors)

        profile.refresh_from_db()
        account.refresh_from_db()
        self.assertEqual(profile.tax_id, "123456789")
        self.assertEqual(account.legal_tax_id_snapshot, "123456789")

    # До первой финансовой операции страницу профиля можно использовать
    # для исправления УНП; снимок счёта меняется вместе с профилем.
    def test_profile_edit_corrects_tax_id_before_financial_activity(self):
        profile = create_test_legal_profile(user=self.user)
        account = create_legal_customer_account(legal_profile=profile)

        self.client.force_login(self.user)
        response = self.client.post(
            self.url,
            data={
                "username": self.user.username,
                "email": self.user.email,
                "is_legal_entity": True,
                "company_name": profile.company_name,
                "tax_id": "987654321",
                "legal_address": profile.legal_address,
                "bank_name": profile.bank_name,
                "bank_account": profile.bank_account,
            },
        )

        self.assertEqual(response.status_code, 302)

        profile.refresh_from_db()
        account.refresh_from_db()
        self.assertEqual(profile.tax_id, "987654321")
        self.assertEqual(account.legal_tax_id_snapshot, "987654321")
        self.assertEqual(account.transactions.count(), 0)