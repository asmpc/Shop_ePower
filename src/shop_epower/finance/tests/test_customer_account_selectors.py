from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_legal_profile,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import (
    CustomerAccount,
    CustomerAccountStatus,
)
from shop_epower.finance.selectors import (
    get_account_status_history,
    get_customer_accounts,
    get_customer_accounts_for_staff,
    get_legal_customer_account,
    get_personal_customer_account,
)
from shop_epower.finance.services import (
    change_customer_account_status,
    create_legal_customer_account,
    create_personal_customer_account,
)


class TestsCustomerAccountSelectors(TestCase):
    # Проверяем получение финансовых счетов пользователя:
    # селектор возвращает его личный и юридический счета,
    # но не возвращает счета другого пользователя.
    def test_get_customer_accounts_returns_only_user_accounts(self):
        user = create_test_user()
        personal_account = create_personal_customer_account(
            user=user,
        )
        legal_profile = create_test_legal_profile(
            user=user,
        )
        legal_account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        other_user = create_test_user()
        create_personal_customer_account(
            user=other_user,
        )

        accounts = get_customer_accounts(
            user=user,
        )

        self.assertCountEqual(
            accounts,
            [
                personal_account,
                legal_account,
            ],
        )

    # Проверяем получение личного финансового счёта:
    # при наличии личного и юридического счетов пользователя
    # селектор возвращает только PERSONAL-счёт.
    def test_get_personal_customer_account_returns_personal_account(self):
        user = create_test_user()
        personal_account = create_personal_customer_account(
            user=user,
        )
        legal_profile = create_test_legal_profile(
            user=user,
        )
        create_legal_customer_account(
            legal_profile=legal_profile,
        )

        account = get_personal_customer_account(
            user=user,
        )

        self.assertEqual(
            account,
            personal_account,
        )

    # Проверяем отсутствие личного финансового счёта:
    # селектор возвращает None и не создаёт недостающий счёт.
    def test_get_personal_customer_account_returns_none_when_missing(self):
        user = create_test_user()

        account = get_personal_customer_account(
            user=user,
        )

        self.assertIsNone(account)
        self.assertFalse(
            CustomerAccount.objects.exists(),
        )

    # Проверяем получение юридического финансового счёта:
    # при наличии личного и юридического счетов пользователя
    # селектор возвращает только LEGAL-счёт.
    def test_get_legal_customer_account_returns_legal_account(self):
        user = create_test_user()
        create_personal_customer_account(
            user=user,
        )
        legal_profile = create_test_legal_profile(
            user=user,
        )
        legal_account = create_legal_customer_account(
            legal_profile=legal_profile,
        )

        account = get_legal_customer_account(
            user=user,
        )

        self.assertEqual(
            account,
            legal_account,
        )

    # Проверяем отсутствие юридического финансового счёта:
    # наличие PERSONAL-счёта не считается результатом,
    # а недостающий LEGAL-счёт не создаётся автоматически.
    def test_get_legal_customer_account_returns_none_when_missing(self):
        user = create_test_user()
        personal_account = create_personal_customer_account(
            user=user,
        )

        account = get_legal_customer_account(
            user=user,
        )

        self.assertIsNone(account)
        self.assertEqual(
            CustomerAccount.objects.count(),
            1,
        )
        self.assertEqual(
            CustomerAccount.objects.get(),
            personal_account,
        )

    # Сотрудник получает счета всех клиентов, включая личные и юридические.
    def test_get_customer_accounts_for_staff_returns_all_accounts(self):
        first_user = create_test_user()
        second_user = create_test_user()

        first_personal = create_personal_customer_account(user=first_user)
        second_personal = create_personal_customer_account(user=second_user)

        legal_profile = create_test_legal_profile(user=first_user)
        first_legal = create_legal_customer_account(legal_profile=legal_profile)

        accounts = get_customer_accounts_for_staff()

        self.assertCountEqual(
            accounts,
            [first_personal, second_personal, first_legal],
        )

    # История статуса относится только к выбранному счёту;
    # последний переход показывается первым.
    def test_get_account_status_history_is_scoped_and_newest_first(self):
        customer = create_test_user()
        other_customer = create_test_user()
        account = create_personal_customer_account(user=customer)
        other_account = create_personal_customer_account(user=other_customer)
        manager = create_test_manager()

        change_customer_account_status(
            account=account,
            new_status=CustomerAccountStatus.INACTIVE,
            reason="Temporary hold.",
            changed_by=manager,
        )
        deactivation = account.status_history.get(
            new_status=CustomerAccountStatus.INACTIVE,
        )

        change_customer_account_status(
            account=account,
            new_status=CustomerAccountStatus.ACTIVE,
            reason="Verification complete.",
            changed_by=manager,
        )
        reactivation = account.status_history.get(
            new_status=CustomerAccountStatus.ACTIVE,
        )

        change_customer_account_status(
            account=other_account,
            new_status=CustomerAccountStatus.INACTIVE,
            reason="Other account hold.",
            changed_by=manager,
        )

        self.assertEqual(
            list(get_account_status_history(account=account)),
            [reactivation, deactivation],
        )
