from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import (
    create_test_legal_profile,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.models import CustomerAccount
from shop_epower.finance.services import (
    create_legal_customer_account,
    create_personal_customer_account,
)
from shop_epower.orders.services import assign_order_funds
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import PaymentMethod
from shop_epower.payments.services import record_manual_order_payment


class TestsProfileBalances(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.url = reverse("accounts:profile")

        self.client.force_login(self.user)

    # Страница профиля получает финансовый счёт пользователя
    # вместе с рассчитанной назначенной предоплатой.
    def test_profile_receives_customer_account_balances(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)

        accounts = list(
            response.context["customer_accounts"]
        )

        self.assertEqual(len(accounts), 1)

        account = accounts[0]

        self.assertEqual(account.pk, self.account.pk)
        self.assertEqual(
            account.assigned_prepayment,
            Decimal("0.00"),
        )

    # Клиент видит на странице профиля доступные деньги,
    # назначенную предоплату и долг своего личного счёта.
    def test_profile_displays_personal_account_balances(self):
        manager = create_test_manager()
        order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
        )

        record_manual_order_payment(
            order=order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="balance:profile:receipt",
            created_by=manager,
        )
        assign_order_funds(
            order=order,
            amount=Decimal("60.00"),
            operation_key="balance:profile:assignment",
            created_by=manager,
        )

        response = self.client.get(self.url)

        self.assertContains(response, "Financial accounts")
        self.assertContains(response, "Personal account")

        currency = self.account.currency

        self.assertContains(
            response,
            f"Available funds: 40.00 {currency}",
        )
        self.assertContains(
            response,
            f"Assigned prepayment: 60.00 {currency}",
        )
        self.assertContains(
            response,
            f"Outstanding debt: 0.00 {currency}",
        )

    # Имя пользователя в навбаре открывает профиль.
    # Из профиля доступен переход к редактированию данных.
    def test_profile_navigation_links_are_available(self):
        response = self.client.get(self.url)

        self.assertContains(
            response,
            f"""
            <a class="nav-link" href="{self.url}">
                {self.user.username}
            </a>
            """,
            html=True,
        )

        edit_url = reverse("accounts:profile_edit")

        self.assertContains(
            response,
            f"""
            <a href="{edit_url}" class="btn btn-outline-dark">
                Edit profile
            </a>
            """,
            html=True,
        )

    # Переданный в адресе ID другого пользователя
    # не меняет владельца показываемых финансовых счетов.
    def test_profile_ignores_another_user_id(self):
        other_user = create_test_user()
        create_personal_customer_account(
            user=other_user,
        )

        response = self.client.get(
            self.url,
            {
                "user_id": other_user.pk,
            },
        )

        self.assertEqual(response.status_code, 200)

        accounts = list(
            response.context["customer_accounts"]
        )

        self.assertEqual(
            [account.pk for account in accounts],
            [self.account.pk],
        )

    # Профиль пользователя без счетов показывает понятное сообщение.
    # Открытие страницы не создаёт финансовый счёт автоматически.
    def test_profile_without_accounts_shows_empty_state(self):
        user_without_account = create_test_user()
        self.client.force_login(user_without_account)

        account_count_before = CustomerAccount.objects.count()

        response = self.client.get(self.url)

        self.assertContains(
            response,
            "No financial accounts yet.",
        )
        self.assertEqual(
            list(response.context["customer_accounts"]),
            [],
        )
        self.assertEqual(
            CustomerAccount.objects.count(),
            account_count_before,
        )

    # Личный и юридический счета показаны отдельно.
    # Для каждого счёта отображаются все три финансовых показателя.
    def test_profile_displays_personal_and_legal_accounts_separately(self):
        profile = create_test_legal_profile(
            user=self.user,
        )
        create_legal_customer_account(
            legal_profile=profile,
        )

        response = self.client.get(self.url)

        self.assertContains(
            response,
            "Personal account",
            count=1,
        )
        self.assertContains(
            response,
            "Legal account",
            count=1,
        )
        self.assertContains(
            response,
            "Available funds:",
            count=2,
        )
        self.assertContains(
            response,
            "Assigned prepayment:",
            count=2,
        )
        self.assertContains(
            response,
            "Outstanding debt:",
            count=2,
        )
