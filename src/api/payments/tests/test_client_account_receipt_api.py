from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from shop_epower.accounts.tests.helpers import (
    create_test_legal_profile,
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import (
    create_legal_customer_account,
    create_personal_customer_account,
)
from shop_epower.payments.models import PaymentMethod, PaymentStatus
from shop_epower.payments.services import (
    cancel_manual_order_payment,
    record_manual_account_payment,
)


class TestsClientAccountReceiptAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

    # Клиент может получить собственное поступление без заказа.
    # Принадлежность определяется через финансовый счёт.
    # API возвращает пустой order_id и идентификатор счёта получателя.
    def test_customer_can_get_own_receipt_without_order(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:client-api-detail",
            created_by=self.manager,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse(
                "api-payments:client-payment-detail",
                kwargs={"payment_id": payment.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], payment.pk)
        self.assertIsNone(response.data["order_id"])
        self.assertEqual(
            response.data["customer_account_id"],
            self.account.pk,
        )
        self.assertEqual(response.data["status"], PaymentStatus.PAID)

    # Другой клиент не может получить чужое поступление без заказа.
    # API ищет платёж только среди доступных ему записей.
    def test_customer_cannot_get_other_customer_receipt(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:client-api-foreign",
            created_by=self.manager,
        )

        other_user = create_test_user()
        self.client.force_authenticate(user=other_user)

        response = self.client.get(
            reverse(
                "api-payments:client-payment-detail",
                kwargs={"payment_id": payment.pk},
            ),
        )

        self.assertEqual(response.status_code, 404)

    # Клиентский список включает собственное поступление без заказа
    # и исключает поступление другого клиента.
    # Каждая запись содержит идентификатор финансового счёта.
    def test_customer_list_returns_only_own_account_receipts(self):
        other_user = create_test_user()
        other_account = create_personal_customer_account(user=other_user)

        receipt_data = {
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "created_by": self.manager,
        }

        payment = record_manual_account_payment(
            account=self.account,
            operation_key="account:receipt:client-list:own",
            **receipt_data,
        )

        record_manual_account_payment(
            account=other_account,
            operation_key="account:receipt:client-list:other",
            **receipt_data,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("api-payments:client-payment-list"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["id"] for item in response.data],
            [payment.pk],
        )
        self.assertIsNone(response.data[0]["order_id"])
        self.assertEqual(
            response.data[0]["customer_account_id"],
            self.account.pk,
        )

    # Другой клиент не может получить историю чужого поступления.
    # Наличие записи об отмене не меняет проверку принадлежности.
    def test_customer_cannot_get_other_customer_receipt_history(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:foreign-history",
            created_by=self.manager,
        )

        cancel_manual_order_payment(
            payment=payment,
            operation_key="account:receipt:foreign-history:reversal",
            created_by=self.manager,
            comment="Receipt registered by mistake.",
        )

        other_user = create_test_user()
        self.client.force_authenticate(user=other_user)

        response = self.client.get(
            reverse(
                "api-payments:client-payment-history",
                kwargs={"payment_id": payment.pk},
            ),
        )

        self.assertEqual(response.status_code, 404)

    # Неавторизованный пользователь не имеет доступа
    # к списку, карточке и истории поступлений.
    def test_anonymous_user_cannot_access_receipt_endpoints(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:anonymous-api",
            created_by=self.manager,
        )

        urls = (
            reverse("api-payments:client-payment-list"),
            reverse(
                "api-payments:client-payment-detail",
                kwargs={"payment_id": payment.pk},
            ),
            reverse(
                "api-payments:client-payment-history",
                kwargs={"payment_id": payment.pk},
            ),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 401)

    # Список различает поступления на личный и юридический счета
    # одного клиента по customer_account_id.
    def test_customer_list_distinguishes_personal_and_legal_receipts(self):
        profile = create_test_legal_profile(user=self.user)
        legal_account = create_legal_customer_account(
            legal_profile=profile,
        )

        receipt_data = {
            "amount": Decimal("100.00"),
            "method": PaymentMethod.ON_RECEIPT,
            "created_by": self.manager,
        }

        personal_payment = record_manual_account_payment(
            account=self.account,
            operation_key="account:receipt:client-list:personal",
            **receipt_data,
        )

        legal_payment = record_manual_account_payment(
            account=legal_account,
            operation_key="account:receipt:client-list:legal",
            **receipt_data,
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse("api-payments:client-payment-list"),
        )

        self.assertEqual(response.status_code, 200)

        accounts_by_payment = {
            item["id"]: item["customer_account_id"]
            for item in response.data
        }

        self.assertEqual(
            accounts_by_payment,
            {
                personal_payment.pk: self.account.pk,
                legal_payment.pk: legal_account.pk,
            },
        )

    # Клиент может получить историю собственного поступления без заказа.
    # История сохраняет переход PAID → CANCELLED.
    def test_customer_can_get_own_receipt_history(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:client-history",
            created_by=self.manager,
        )

        cancel_manual_order_payment(
            payment=payment,
            operation_key="account:receipt:client-history:reversal",
            created_by=self.manager,
            comment="Receipt registered by mistake.",
        )

        self.client.force_authenticate(user=self.user)

        response = self.client.get(
            reverse(
                "api-payments:client-payment-history",
                kwargs={"payment_id": payment.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(
            response.data[0]["old_status"],
            PaymentStatus.PAID,
        )
        self.assertEqual(
            response.data[0]["new_status"],
            PaymentStatus.CANCELLED,
        )
