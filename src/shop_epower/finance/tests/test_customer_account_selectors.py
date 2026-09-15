from django.test import TestCase

from shop_epower.accounts.tests.helpers import (
    create_test_legal_profile,
    create_test_user,
)
from shop_epower.finance.models import CustomerAccount
from shop_epower.finance.selectors import (
    get_customer_accounts,
    get_legal_customer_account,
    get_personal_customer_account,
)
from shop_epower.finance.services import (
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
