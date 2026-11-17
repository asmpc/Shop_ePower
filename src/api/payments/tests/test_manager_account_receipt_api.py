from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.payments.models import PaymentMethod
from shop_epower.payments.services import record_manual_account_payment


class TestsManagerAccountReceiptAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

    # Менеджер получает поступление без заказа.
    # Ответ содержит финансовый счёт и email владельца денег.
    def test_manager_can_get_receipt_without_order(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:manager-api-detail",
            created_by=self.manager,
        )

        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse(
                "api-payments:manager-payment-detail",
                kwargs={"pk": payment.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], payment.pk)
        self.assertIsNone(response.data["order"])
        self.assertEqual(
            response.data["customer_account_id"],
            self.account.pk,
        )
        self.assertEqual(response.data["customer_email"], self.user.email)

    # Служебный список показывает поступление без заказа
    # вместе с финансовым счётом и email клиента.
    def test_manager_list_identifies_receipt_without_order(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:manager-api-list",
            created_by=self.manager,
        )

        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            reverse("api-payments:manager-payment-list"),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)

        item = response.data[0]

        self.assertEqual(item["id"], payment.pk)
        self.assertIsNone(item["order"])
        self.assertEqual(item["customer_account_id"], self.account.pk)
        self.assertEqual(item["customer_email"], self.user.email)

    # Клиент не может открывать служебные список и карточку,
    # даже если поступление принадлежит его собственному счёту.
    def test_customer_cannot_access_staff_receipt_endpoints(self):
        payment = record_manual_account_payment(
            account=self.account,
            amount=Decimal("100.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="account:receipt:manager-api-forbidden",
            created_by=self.manager,
        )

        self.client.force_authenticate(user=self.user)

        urls = (
            reverse("api-payments:manager-payment-list"),
            reverse(
                "api-payments:manager-payment-detail",
                kwargs={"pk": payment.pk},
            ),
        )

        for url in urls:
            with self.subTest(url=url):
                response = self.client.get(url)

                self.assertEqual(response.status_code, 403)
