from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.models import LegalProfile, User
from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_legal_profile,
    create_test_manager,
    create_test_user,
)
from shop_epower.core.currency import get_base_currency
from shop_epower.finance.models import (
    CustomerAccount,
    CustomerAccountStatus,
    CustomerAccountType,
)
from shop_epower.finance.services import (
    change_customer_account_status,
    create_legal_customer_account,
    create_personal_customer_account,
)


class TestsCustomerAccountServices(TestCase):
    def setUp(self):
        self.user = create_test_user(
            email="finance-service-client@test.com",
            username="finance-service-client",
            password="testpass123",
        )

    # Проверяем создание личного финансового счёта:
    # сервис создаёт для зарегистрированного пользователя один активный
    # PERSONAL-счёт в базовой валюте, без юрпрофиля и с нулевыми балансами.
    def test_create_personal_customer_account_creates_active_account(self):
        account = create_personal_customer_account(
            user=self.user,
        )

        self.assertEqual(
            CustomerAccount.objects.count(),
            1,
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
            account.legal_tax_id_snapshot,
            "",
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

    # Проверяем идемпотентность создания личного счёта:
    # повторный вызов возвращает тот же счёт
    # и не создаёт дополнительную запись.
    def test_create_personal_customer_account_returns_existing_account(self):
        first_account = create_personal_customer_account(
            user=self.user,
        )

        second_account = create_personal_customer_account(
            user=self.user,
        )

        self.assertEqual(
            second_account,
            first_account,
        )
        self.assertEqual(
            CustomerAccount.objects.count(),
            1,
        )

    # Проверяем независимость финансового счёта от роли:
    # менеджер, действующий как покупатель,
    # может получить личный финансовый счёт.
    def test_create_personal_customer_account_allows_manager(self):
        manager = create_test_manager(
            email="finance-service-manager@test.com",
            username="finance-service-manager",
            password="testpass123",
        )

        account = create_personal_customer_account(
            user=manager,
        )

        self.assertEqual(
            account.user,
            manager,
        )
        self.assertEqual(
            account.account_type,
            CustomerAccountType.PERSONAL,
        )

    # Проверяем независимость финансового счёта от роли:
    # администратор, действующий как покупатель,
    # может получить личный финансовый счёт.
    def test_create_personal_customer_account_allows_admin(self):
        admin = create_test_admin(
            email="finance-service-admin@test.com",
            username="finance-service-admin",
            password="testpass123",
        )

        account = create_personal_customer_account(
            user=admin,
        )

        self.assertEqual(
            account.user,
            admin,
        )
        self.assertEqual(
            account.account_type,
            CustomerAccountType.PERSONAL,
        )

    # Проверяем, что финансовый счёт нельзя создать
    # для пользователя, который ещё не сохранён в базе данных.
    def test_create_personal_customer_account_rejects_unsaved_user(self):
        unsaved_user = User(
            email="unsaved-finance-user@test.com",
            username="unsaved-finance-user",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "User must be saved before creating a customer account.",
        ):
            create_personal_customer_account(
                user=unsaved_user,
            )

    # Проверяем создание финансового счёта юридического лица:
    # сервис связывает счёт с юридическим профилем,
    # сохраняет снимок УНП/ИНН и устанавливает начальные значения.
    def test_create_legal_customer_account_creates_active_account(self):
        legal_profile = create_test_legal_profile(
            user=self.user,
        )

        account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        self.assertEqual(
            CustomerAccount.objects.count(),
            1,
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
            legal_profile.tax_id,
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

    # Проверяем идемпотентность создания юридического счёта:
    # повторный вызов с тем же юридическим профилем
    # возвращает существующий счёт и не создаёт новый.
    def test_create_legal_customer_account_returns_existing_account(self):
        legal_profile = create_test_legal_profile(
            user=self.user,
        )

        first_account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        second_account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        self.assertEqual(
            second_account,
            first_account,
        )
        self.assertEqual(
            CustomerAccount.objects.count(),
            1,
        )

    # Проверяем, что юридический финансовый счёт нельзя создать,
    # если в профиле не включено оформление от юридического лица.
    def test_create_legal_customer_account_requires_legal_entity_profile(self):
        legal_profile = create_test_legal_profile(
            user=self.user,
            is_legal_entity=False,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Legal profile must be enabled for legal purchasing.",
        ):
            create_legal_customer_account(
                legal_profile=legal_profile,
            )

    # Проверяем, что для создания юридического счёта
    # требуется непустое название организации.
    def test_create_legal_customer_account_requires_company_name(self):
        legal_profile = create_test_legal_profile(
            user=self.user,
            company_name="   ",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Company name is required to create a legal customer account.",
        ):
            create_legal_customer_account(
                legal_profile=legal_profile,
            )

    # Проверяем, что для создания юридического счёта
    # требуется непустой УНП/ИНН организации.
    def test_create_legal_customer_account_requires_tax_id(self):
        legal_profile = create_test_legal_profile(
            user=self.user,
            tax_id="   ",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Tax ID is required to create a legal customer account.",
        ):
            create_legal_customer_account(
                legal_profile=legal_profile,
            )

    # Проверяем, что для создания юридического счёта
    # требуется непустой юридический адрес организации.
    def test_create_legal_customer_account_requires_legal_address(self):
        legal_profile = create_test_legal_profile(
            user=self.user,
            legal_address="   ",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Legal address is required to create a legal customer account.",
        ):
            create_legal_customer_account(
                legal_profile=legal_profile,
            )

    # Проверяем, что юридический счёт нельзя создать
    # для юридического профиля, который ещё не сохранён в базе.
    def test_create_legal_customer_account_rejects_unsaved_profile(self):
        unsaved_legal_profile = LegalProfile(
            user=self.user,
            is_legal_entity=True,
            company_name="Unsaved Company",
            tax_id="987654321",
            legal_address="Minsk, Unsaved street 1",
            bank_name="Test Bank",
            bank_account="BY00TEST0000000000000000000000",
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Legal profile must be saved before creating a legal customer account.",
        ):
            create_legal_customer_account(
                legal_profile=unsaved_legal_profile,
            )

    # Проверяем независимость юридического счёта от роли:
    # менеджер, действующий как покупатель от организации,
    # может получить юридический финансовый счёт.
    def test_create_legal_customer_account_allows_manager(self):
        manager = create_test_manager()
        legal_profile = create_test_legal_profile(
            user=manager,
        )

        account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        self.assertEqual(
            account.user,
            manager,
        )
        self.assertEqual(
            account.account_type,
            CustomerAccountType.LEGAL,
        )
        self.assertEqual(
            account.legal_profile,
            legal_profile,
        )

    # Проверяем независимость юридического счёта от роли:
    # администратор, действующий как покупатель от организации,
    # может получить юридический финансовый счёт.
    def test_create_legal_customer_account_allows_admin(self):
        admin = create_test_admin()
        legal_profile = create_test_legal_profile(
            user=admin,
        )

        account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        self.assertEqual(
            account.user,
            admin,
        )
        self.assertEqual(
            account.account_type,
            CustomerAccountType.LEGAL,
        )
        self.assertEqual(
            account.legal_profile,
            legal_profile,
        )

    # Проверяем неизменность снимка УНП/ИНН:
    # изменение юридического профиля и повторный вызов сервиса
    # не переписывают идентичность существующего финансового счёта.
    def test_create_legal_customer_account_preserves_tax_id_snapshot(self):
        legal_profile = create_test_legal_profile(
            user=self.user,
            tax_id="123456789",
        )

        account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        legal_profile.tax_id = "987654321"
        legal_profile.save(
            update_fields=[
                "tax_id",
            ]
        )

        repeated_account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        account.refresh_from_db()

        self.assertEqual(
            repeated_account,
            account,
        )
        self.assertEqual(
            account.legal_tax_id_snapshot,
            "123456789",
        )
        self.assertEqual(
            legal_profile.tax_id,
            "987654321",
        )

    # Проверяем деактивацию финансового счёта:
    # сервис меняет статус счёта и сохраняет отдельную запись
    # с предыдущим и новым статусами, причиной и сотрудником.
    def test_change_customer_account_status_deactivates_account_and_creates_history(
        self,
    ):
        account = create_personal_customer_account(
            user=self.user,
        )
        manager = create_test_manager()

        changed_account = change_customer_account_status(
            account=account,
            new_status=CustomerAccountStatus.INACTIVE,
            reason="Customer requested account deactivation.",
            changed_by=manager,
        )

        account.refresh_from_db()

        self.assertEqual(
            changed_account,
            account,
        )
        self.assertEqual(
            account.status,
            CustomerAccountStatus.INACTIVE,
        )

        history = account.status_history.get()

        self.assertEqual(
            history.old_status,
            CustomerAccountStatus.ACTIVE,
        )
        self.assertEqual(
            history.new_status,
            CustomerAccountStatus.INACTIVE,
        )
        self.assertEqual(
            history.reason,
            "Customer requested account deactivation.",
        )
        self.assertEqual(
            history.changed_by,
            manager,
        )

    # Проверяем атомарность изменения статуса:
    # если запись истории не создалась, изменение статуса счёта
    # также должно быть отменено.
    def test_change_customer_account_status_rolls_back_when_history_creation_fails(
        self,
    ):
        account = create_personal_customer_account(
            user=self.user,
        )

        with patch(
            "shop_epower.finance.services.customer_account."
            "CustomerAccountStatusHistory.objects.create",
            side_effect=RuntimeError("History creation failed."),
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "History creation failed.",
            ):
                change_customer_account_status(
                    account=account,
                    new_status=CustomerAccountStatus.INACTIVE,
                    reason="Testing transaction rollback.",
                )

        account.refresh_from_db()

        self.assertEqual(
            account.status,
            CustomerAccountStatus.ACTIVE,
        )
        self.assertFalse(
            account.status_history.exists(),
        )

    # Проверяем повторную активацию финансового счёта:
    # сервис переводит счёт из INACTIVE в ACTIVE
    # и сохраняет этот переход отдельной записью истории.
    def test_change_customer_account_status_reactivates_account_and_creates_history(
        self,
    ):
        account = create_personal_customer_account(
            user=self.user,
        )
        manager = create_test_manager()
        admin = create_test_admin()

        change_customer_account_status(
            account=account,
            new_status=CustomerAccountStatus.INACTIVE,
            reason="Temporary account deactivation.",
            changed_by=manager,
        )

        changed_account = change_customer_account_status(
            account=account,
            new_status=CustomerAccountStatus.ACTIVE,
            reason="Account reactivated after verification.",
            changed_by=admin,
        )

        account.refresh_from_db()

        self.assertEqual(
            changed_account,
            account,
        )
        self.assertEqual(
            account.status,
            CustomerAccountStatus.ACTIVE,
        )
        self.assertEqual(
            account.status_history.count(),
            2,
        )

        reactivation_history = account.status_history.get(
            new_status=CustomerAccountStatus.ACTIVE,
        )

        self.assertEqual(
            reactivation_history.old_status,
            CustomerAccountStatus.INACTIVE,
        )
        self.assertEqual(
            reactivation_history.reason,
            "Account reactivated after verification.",
        )
        self.assertEqual(
            reactivation_history.changed_by,
            admin,
        )

    # Проверяем, что повторная установка текущего статуса запрещена:
    # переход ACTIVE → ACTIVE не изменяет счёт
    # и не создаёт фиктивную запись истории.
    def test_change_customer_account_status_rejects_same_status(self):
        account = create_personal_customer_account(
            user=self.user,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Customer account already has the requested status.",
        ):
            change_customer_account_status(
                account=account,
                new_status=CustomerAccountStatus.ACTIVE,
                reason="Redundant status change.",
            )

        account.refresh_from_db()

        self.assertEqual(
            account.status,
            CustomerAccountStatus.ACTIVE,
        )
        self.assertFalse(
            account.status_history.exists(),
        )

    # Проверяем обязательность причины изменения статуса:
    # пустая причина не изменяет счёт
    # и не создаёт запись истории.
    def test_change_customer_account_status_requires_reason(self):
        account = create_personal_customer_account(
            user=self.user,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Status change reason is required.",
        ):
            change_customer_account_status(
                account=account,
                new_status=CustomerAccountStatus.INACTIVE,
                reason="   ",
            )

        account.refresh_from_db()

        self.assertEqual(
            account.status,
            CustomerAccountStatus.ACTIVE,
        )
        self.assertFalse(
            account.status_history.exists(),
        )

    # Проверяем допустимость нового статуса:
    # неизвестное значение не сохраняется в счёте
    # и не попадает в историю статусов.
    def test_change_customer_account_status_rejects_unknown_status(self):
        account = create_personal_customer_account(
            user=self.user,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Unsupported customer account status.",
        ):
            change_customer_account_status(
                account=account,
                new_status="blocked",
                reason="Testing an unsupported status.",
            )

        account.refresh_from_db()

        self.assertEqual(
            account.status,
            CustomerAccountStatus.ACTIVE,
        )
        self.assertFalse(
            account.status_history.exists(),
        )

    # Проверяем работу с актуальным состоянием базы:
    # если статус был изменён после загрузки Python-объекта,
    # сервис не создаёт повторный переход на тот же статус.
    def test_change_customer_account_status_uses_current_database_status(self):
        account = create_personal_customer_account(
            user=self.user,
        )

        CustomerAccount.objects.filter(
            pk=account.pk,
        ).update(
            status=CustomerAccountStatus.INACTIVE,
        )

        # Объект account в памяти всё ещё содержит старый статус ACTIVE.
        self.assertEqual(
            account.status,
            CustomerAccountStatus.ACTIVE,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Customer account already has the requested status.",
        ):
            change_customer_account_status(
                account=account,
                new_status=CustomerAccountStatus.INACTIVE,
                reason="Repeated deactivation from a stale object.",
            )

        account.refresh_from_db()

        self.assertEqual(
            account.status,
            CustomerAccountStatus.INACTIVE,
        )
        self.assertFalse(
            account.status_history.exists(),
        )

    # Проверяем, что статус нельзя изменить у несохранённого счёта:
    # финансовый счёт должен существовать в базе данных.
    def test_change_customer_account_status_rejects_unsaved_account(self):
        account = CustomerAccount(
            user=self.user,
            account_type=CustomerAccountType.PERSONAL,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Customer account must be saved before changing its status.",
        ):
            change_customer_account_status(
                account=account,
                new_status=CustomerAccountStatus.INACTIVE,
                reason="Attempt to deactivate an unsaved account.",
            )
