from decimal import Decimal

from django.urls import reverse
from rest_framework.test import APITestCase

from shop_epower.accounts.tests.helpers import (
    create_test_legal_profile,
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.models import CustomerAccount
from shop_epower.finance.services import (
    create_legal_customer_account,
    create_personal_customer_account,
)
from shop_epower.orders.models import OrderItem, OrderStatus
from shop_epower.orders.services import (
    assign_order_funds,
    complete_order_shipment,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import PaymentMethod
from shop_epower.payments.services import record_manual_order_payment


class TestsAccountBalancesAPI(APITestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            total_price=Decimal("100.00"),
        )
        self.url = reverse("api-account-balances")

        self.client.force_authenticate(user=self.user)

    def _create_prepayment_assignment(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="balance:api:receipt",
            created_by=self.manager,
        )
        return assign_order_funds(
            order=self.order,
            amount=Decimal("60.00"),
            operation_key="balance:api:assignment",
            created_by=self.manager,
        )

    # API возвращает существующий счёт пользователя без операций.
    # Денежные показатели представлены строками с двумя знаками.
    def test_returns_account_with_zero_balances(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.data,
            [
                {
                    "id": self.account.pk,
                    "account_type": self.account.account_type,
                    "status": self.account.status,
                    "currency": self.account.currency,
                    "available_balance": "0.00",
                    "assigned_prepayment": "0.00",
                    "debt_balance": "0.00",
                },
            ],
        )

    # Неавторизованный запрос не получает финансовые данные.
    def test_balances_require_authentication(self):
        self.client.force_authenticate(user=None)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 401)

    # API возвращает только собственные счета пользователя.
    # Чужой user_id в параметрах запроса не меняет выборку.
    def test_returns_only_authenticated_user_accounts(self):
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
        self.assertEqual(
            [account["id"] for account in response.data],
            [self.account.pk],
        )

    # API показывает доступный остаток и назначенную предоплату.
    # До отгрузки назначение денег не создаёт долг.
    def test_returns_available_funds_and_assigned_prepayment(self):
        self._create_prepayment_assignment()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        account_data = response.data[0]

        self.assertEqual(account_data["available_balance"], "40.00")
        self.assertEqual(account_data["assigned_prepayment"], "60.00")
        self.assertEqual(account_data["debt_balance"], "0.00")

    # После отгрузки использованные деньги исключаются из предоплаты.
    # API показывает неизменный доступный остаток и непогашенный долг.
    def test_returns_balances_after_shipment(self):
        self._create_prepayment_assignment()

        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        product = create_test_product()
        OrderItem.objects.create(
            order=self.order,
            product=product,
            product_name=product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

        complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        account_data = response.data[0]

        self.assertEqual(account_data["available_balance"], "40.00")
        self.assertEqual(account_data["assigned_prepayment"], "0.00")
        self.assertEqual(account_data["debt_balance"], "40.00")

    # Пользователь без счетов получает пустой список.
    # Получение балансов не создаёт финансовый счёт.
    def test_user_without_accounts_gets_empty_list(self):
        user_without_account = create_test_user()
        self.client.force_authenticate(user=user_without_account)

        account_count_before = CustomerAccount.objects.count()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])
        self.assertEqual(
            CustomerAccount.objects.count(),
            account_count_before,
        )

    # API возвращает личный и юридический счета раздельно.
    # Каждый счёт сохраняет собственные показатели и валюту.
    def test_returns_personal_and_legal_accounts_separately(self):
        self._create_prepayment_assignment()

        profile = create_test_legal_profile(
            user=self.user,
        )
        legal_account = create_legal_customer_account(
            legal_profile=profile,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 2)

        accounts = {
            account["account_type"]: account
            for account in response.data
        }
        personal_data = accounts["personal"]
        legal_data = accounts["legal"]

        self.assertEqual(personal_data["id"], self.account.pk)
        self.assertEqual(personal_data["currency"], self.account.currency)
        self.assertEqual(personal_data["available_balance"], "40.00")
        self.assertEqual(personal_data["assigned_prepayment"], "60.00")
        self.assertEqual(personal_data["debt_balance"], "0.00")

        self.assertEqual(legal_data["id"], legal_account.pk)
        self.assertEqual(legal_data["currency"], legal_account.currency)
        self.assertEqual(legal_data["available_balance"], "0.00")
        self.assertEqual(legal_data["assigned_prepayment"], "0.00")
        self.assertEqual(legal_data["debt_balance"], "0.00")

    # Адрес балансов отклоняет запросы изменения данных.
    # Балансы и финансовая история остаются без изменений.
    def test_balances_endpoint_is_read_only(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)(
                    self.url,
                    {
                        "available_balance": "999.00",
                        "assigned_prepayment": "999.00",
                        "debt_balance": "999.00",
                    },
                    format="json",
                )

                self.assertEqual(response.status_code, 405)

        self.account.refresh_from_db()

        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.account.transactions.exists())
