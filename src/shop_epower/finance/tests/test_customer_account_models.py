from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from shop_epower.accounts.models import LegalProfile
from shop_epower.accounts.tests.helpers import create_test_user
from shop_epower.core.currency import get_base_currency
from shop_epower.finance.models import (
    CustomerAccount,
    CustomerAccountStatus,
    CustomerAccountType,
)


class TestsCustomerAccountModel(TestCase):
    def setUp(self):
        self.user = create_test_user(
            email="finance-client@test.com",
            username="finance-client",
            password="testpass123",
        )

    # Проверяем начальное состояние личного финансового счёта:
    # счёт принадлежит клиенту, не связан с юридическим профилем,
    # использует базовую валюту и имеет нулевые балансы.
    def test_personal_customer_account_can_be_created(self):
        account = CustomerAccount.objects.create(
            user=self.user,
            account_type=CustomerAccountType.PERSONAL,
        )

        self.assertEqual(
            account.user,
            self.user,
        )

        self.assertEqual(
            account.account_type,
            CustomerAccountType.PERSONAL,
        )

        self.assertIsNone(
            account.legal_profile,
        )

        self.assertEqual(
            account.currency,
            get_base_currency(),
        )

        self.assertEqual(
            account.available_balance,
            Decimal("0.00"),
        )

        self.assertEqual(
            account.debt_balance,
            Decimal("0.00"),
        )

        self.assertEqual(
            account.status,
            CustomerAccountStatus.ACTIVE,
        )

    # Проверяем создание финансового счёта юридического лица:
    # счёт связан с юридическим профилем и сохраняет снимок УНП/ИНН,
    # чтобы последующее изменение профиля не изменило финансовую историю.
    def test_legal_customer_account_can_be_created(self):
        legal_profile = LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=True,
            company_name="Test Company LLC",
            tax_id="123456789",
            legal_address="Test legal address",
            bank_name="Test Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
        )

        account = CustomerAccount.objects.create(
            user=self.user,
            account_type=CustomerAccountType.LEGAL,
            legal_profile=legal_profile,
            legal_tax_id_snapshot=legal_profile.tax_id,
        )

        self.assertEqual(
            account.user,
            self.user,
        )
        self.assertEqual(
            account.account_type,
            CustomerAccountType.LEGAL,
        )
        self.assertEqual(
            account.legal_profile,
            legal_profile,
        )
        self.assertEqual(
            account.legal_tax_id_snapshot,
            "123456789",
        )

    # Проверяем ограничение уникальности:
    # у одного пользователя не может быть двух финансовых счетов
    # одного и того же типа.
    def test_user_cannot_have_two_accounts_of_same_type(self):
        CustomerAccount.objects.create(
            user=self.user,
            account_type=CustomerAccountType.PERSONAL,
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerAccount.objects.create(
                    user=self.user,
                    account_type=CustomerAccountType.PERSONAL,
                )

    # Проверяем финансовый инвариант:
    # доступный баланс счёта не может быть отрицательным.
    def test_available_balance_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerAccount.objects.create(
                    user=self.user,
                    account_type=CustomerAccountType.PERSONAL,
                    available_balance=Decimal("-0.01"),
                )

    # Проверяем финансовый инвариант:
    # остаток долга не может быть отрицательным.
    def test_debt_balance_cannot_be_negative(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerAccount.objects.create(
                    user=self.user,
                    account_type=CustomerAccountType.PERSONAL,
                    debt_balance=Decimal("-0.01"),
                )

    # Проверяем согласованность личного счёта:
    # личный финансовый счёт не может быть связан
    # с юридическим профилем пользователя.
    def test_personal_account_cannot_reference_legal_profile(self):
        legal_profile = LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=True,
            company_name="Test Company LLC",
            tax_id="123456789",
            legal_address="Test legal address",
            bank_name="Test Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerAccount.objects.create(
                    user=self.user,
                    account_type=CustomerAccountType.PERSONAL,
                    legal_profile=legal_profile,
                )

    # Проверяем согласованность юридического счёта:
    # юридический финансовый счёт обязан быть связан
    # с юридическим профилем пользователя.
    def test_legal_account_requires_legal_profile(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerAccount.objects.create(
                    user=self.user,
                    account_type=CustomerAccountType.LEGAL,
                    legal_tax_id_snapshot="123456789",
                )

    # Проверяем согласованность личного счёта:
    # личный счёт не может содержать снимок налогового номера организации.
    def test_personal_account_cannot_have_legal_tax_id_snapshot(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerAccount.objects.create(
                    user=self.user,
                    account_type=CustomerAccountType.PERSONAL,
                    legal_tax_id_snapshot="123456789",
                )

    # Проверяем согласованность юридического счёта:
    # юридический счёт обязан хранить снимок налогового номера.
    def test_legal_account_requires_legal_tax_id_snapshot(self):
        legal_profile = LegalProfile.objects.create(
            user=self.user,
            is_legal_entity=True,
            company_name="Test Company LLC",
            tax_id="123456789",
            legal_address="Test legal address",
            bank_name="Test Bank",
            bank_account="BY00 TEST 0000 0000 0000 0000 0000",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                CustomerAccount.objects.create(
                    user=self.user,
                    account_type=CustomerAccountType.LEGAL,
                    legal_profile=legal_profile,
                )

    # Проверяем аудит времени:
    # финансовый счёт сохраняет время создания
    # и время последнего обновления текущей проекции.
    def test_customer_account_has_timestamps(self):
        account = CustomerAccount.objects.create(
            user=self.user,
            account_type=CustomerAccountType.PERSONAL,
        )

        self.assertIsNotNone(
            account.created_at,
        )
        self.assertIsNotNone(
            account.updated_at,
        )

    # Проверяем, что для поиска счетов пользователя
    # по статусу определён составной индекс.
    def test_customer_account_has_user_status_index(self):
        index_fields = [tuple(index.fields) for index in CustomerAccount._meta.indexes]

        self.assertIn(
            ("user", "status"),
            index_fields,
        )
