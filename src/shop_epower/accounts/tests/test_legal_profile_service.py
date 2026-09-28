from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.models import LegalProfile
from shop_epower.accounts.services import save_legal_profile
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


class TestsLegalProfileService(TestCase):
    # Активация заполненного юрпрофиля создаёт отдельный юридический счёт.
    def test_valid_activation_creates_legal_account(self):
        user = create_test_user()

        profile = save_legal_profile(
            user=user,
            data={
                "is_legal_entity": True,
                "company_name": "Test Company",
                "tax_id": "123456789",
                "legal_address": "Minsk",
                "bank_name": "Test Bank",
                "bank_account": "BY00TEST123456",
            },
        )

        self.assertEqual(profile, LegalProfile.objects.get(user=user))
        self.assertTrue(profile.is_legal_entity)

        account = CustomerAccount.objects.get(
            user=user,
            account_type=CustomerAccountType.LEGAL,
        )
        self.assertEqual(account.legal_profile, profile)
        self.assertEqual(account.legal_tax_id_snapshot, "123456789")

    # Ошибка создания счёта откатывает сохранение юрпрофиля.
    def test_save_legal_profile_rolls_back_when_account_creation_fails(self):
        user = create_test_user()

        with patch(
            "shop_epower.accounts.services.legal_profile.create_legal_customer_account",
            side_effect=RuntimeError("Account creation failed."),
        ):
            with self.assertRaisesMessage(RuntimeError, "Account creation failed."):
                save_legal_profile(
                    user=user,
                    data={
                        "is_legal_entity": True,
                        "company_name": "Test Company",
                        "tax_id": "123456789",
                        "legal_address": "Minsk",
                        "bank_name": "Test Bank",
                        "bank_account": "BY00TEST123456",
                    },
                )

        self.assertFalse(LegalProfile.objects.filter(user=user).exists())
        self.assertFalse(CustomerAccount.objects.filter(user=user).exists())

    # После финансовой операции нельзя заменить УНП/ИНН юрпрофиля.
    def test_tax_id_cannot_change_after_financial_activity(self):
        user = create_test_user()
        profile = create_test_legal_profile(user=user)
        account = create_legal_customer_account(legal_profile=profile)

        record_customer_deposit(
            account=account,
            amount=Decimal("10.00"),
            operation_key="legal-identity:test:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Legal tax ID cannot be changed after financial activity.",
        ):
            save_legal_profile(
                user=user,
                data={"tax_id": "987654321"},
            )

        profile.refresh_from_db()
        self.assertEqual(profile.tax_id, "123456789")

    # До первой операции УНП можно исправить без создания нового счёта.
    def test_tax_id_change_before_financial_activity_updates_account_snapshot(self):
        user = create_test_user()
        profile = create_test_legal_profile(user=user)
        account = create_legal_customer_account(legal_profile=profile)

        saved_profile = save_legal_profile(
            user=user,
            data={"tax_id": "987654321"},
        )

        account.refresh_from_db()

        self.assertEqual(saved_profile.tax_id, "987654321")
        self.assertEqual(account.legal_tax_id_snapshot, "987654321")
        self.assertEqual(
            CustomerAccount.objects.filter(
                user=user,
                account_type=CustomerAccountType.LEGAL,
            ).count(),
            1,
        )

    # Выключение юрпокупок не стирает реквизиты и не удаляет счёт.
    def test_disabling_legal_purchasing_preserves_details_and_account(self):
        user = create_test_user()
        profile = create_test_legal_profile(user=user)
        account = create_legal_customer_account(legal_profile=profile)

        record_customer_deposit(
            account=account,
            amount=Decimal("10.00"),
            operation_key="legal-disable:test:001",
            actor_type=AccountTransactionActorType.SYSTEM,
        )

        saved_profile = save_legal_profile(
            user=user,
            data={
                "is_legal_entity": False,
                "company_name": "",
                "tax_id": "",
                "legal_address": "",
                "bank_name": "",
                "bank_account": "",
            },
        )

        self.assertFalse(saved_profile.is_legal_entity)
        self.assertEqual(saved_profile.company_name, "Test Company")
        self.assertEqual(saved_profile.tax_id, "123456789")
        self.assertTrue(CustomerAccount.objects.filter(pk=account.pk).exists())

        account.refresh_from_db()
        self.assertEqual(account.legal_tax_id_snapshot, "123456789")
        self.assertEqual(account.transactions.count(), 1)
