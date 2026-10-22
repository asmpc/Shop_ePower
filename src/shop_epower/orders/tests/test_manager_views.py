from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.core.currency import get_base_currency
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import Order, OrderItem, OrderStatus
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    InvoiceStatus,
    PaymentMethod,
    PaymentProvider,
    PaymentStatus,
)
from shop_epower.payments.services import mark_payment_paid
from shop_epower.payments.tests.helpers import (
    create_test_invoice,
    create_test_payment,
)


class TestsManagerOrderViews(TestCase):

    def setUp(self):
        self.manager = create_test_manager(
            email="frontend-manager@example.com",
            username="frontend-manager",
            password="testpass123",
            role="manager",
        )

        self.admin = create_test_admin(
            email="admin@test.com",
            username="admin",
            password="testpass123",
            role="admin",
        )

        self.client_user = create_test_user(
            email="frontend-client@example.com",
            username="frontend-client",
            password="testpass123",
            role="client",
        )

        self.account = create_personal_customer_account(
            user=self.client_user,
        )

        self.order = Order.objects.create(
            user=self.client_user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            payment_method=PaymentMethod.INVOICE,
            is_legal_entity=False,
            customer_name="Frontend Client",
            customer_email="frontend-client@example.com",
            customer_phone="+10000000040",
            total_price=Decimal("100.00"),
            delivery_method="shipping",
            delivery_provider="post",
            delivery_address="Frontend address",
            delivery_comment="Frontend comment",
        )

        self.payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            status=PaymentStatus.PENDING,
            provider=PaymentProvider.MANUAL,
            amount=self.order.total_price,
            currency_snapshot=get_base_currency(),
        )

        self.product = create_test_product(
            name="Frontend Delivery Product",
            brand_name="Frontend Delivery Brand",
            category_name="Frontend Delivery Category",
            manufacturer_article="FRONTEND-DELIVERY-001",
            base_price=Decimal("100.00"),
        )

        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

    def get_manager_order_list_url(self):
        return reverse(
            "orders:manager_order_list",
        )

    def get_expected_manager_order_detail_url(self):
        manager_order_list_url = (
            self.get_manager_order_list_url()
        )

        manager_order_detail_url = reverse(
            "orders:manager_order_detail",
            args=[self.order.id],
        )

        return (
            f"{manager_order_detail_url}?"
            f"{urlencode({'next': manager_order_list_url})}"
        )


    # Проверяем manager detail page:
    # для заказа в статусе PROCESSING
    # отображаются кнопки Complete order и Cancel order.
    def test_manager_detail_page_shows_cancel_button_for_processing_order(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Complete order")
        self.assertContains(response, "Cancel order")

    # Проверяем manager frontend workflow:
    # менеджер может отменить заказ
    # в статусе PROCESSING через frontend form.
    def test_manager_can_cancel_processing_order_from_frontend(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "orders:manager_order_status_update",
                kwargs={"pk": self.order.pk},
            ),
            {
                "status": OrderStatus.CANCELLED,
                "cancellation_reason": "client_refused",
                "cancellation_comment": "Client changed their mind.",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.CANCELLED,
        )
        self.assertEqual(
            self.order.cancellation_reason,
            "client_refused",
        )

        self.assertEqual(
            self.order.cancellation_comment,
            "Client changed their mind.",
        )

    # Проверяем отображение cancellation info:
    # после отмены заказа manager detail page
    # показывает причину и комментарий отмены.
    def test_manager_detail_page_shows_cancellation_info(self):
        self.order.status = OrderStatus.CANCELLED
        self.order.cancellation_reason = "delivery_cost"
        self.order.cancellation_comment = "Delivery price was too high."
        self.order.save(
            update_fields=[
                "status",
                "cancellation_reason",
                "cancellation_comment",
            ]
        )

        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delivery cost")
        self.assertContains(response, "Delivery price was too high.")

    # Проверяем delivery display:
    # manager order detail page показывает delivery информацию.
    def test_manager_order_detail_page_shows_delivery_info(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Shipping")
        self.assertContains(response, "Post")
        self.assertContains(response, "Frontend address")
        self.assertContains(response, "Frontend comment")

    # Проверяем manager delivery frontend pricing:
    # manager может обновить стоимость доставки через форму,
    # и delivery cost прибавляется к total_price.
    def test_manager_can_update_delivery_cost_from_frontend(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "orders:manager_order_delivery_update",
                kwargs={"pk": self.order.pk},
            ),
            {
                "delivery_cost": "25.00",
                "manager_delivery_comment": "Delivery included.",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_cost,
            Decimal("25.00"),
        )

        self.assertEqual(
            self.order.total_price,
            Decimal("125.00"),
        )

    # Проверяем manager delivery frontend pricing:
    # если manager отмечает оплату доставки при получении,
    # delivery cost сохраняется, но total_price не меняется.
    def test_manager_can_mark_delivery_as_paid_on_receipt_from_frontend(self):
        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "orders:manager_order_delivery_update",
                kwargs={"pk": self.order.pk},
            ),
            {
                "delivery_cost": "25.00",
                "delivery_paid_by_customer_on_receipt": "on",
                "manager_delivery_comment": "Customer pays on receipt.",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()

        self.assertEqual(
            self.order.delivery_cost,
            Decimal("25.00"),
        )

        self.assertEqual(
            self.order.total_price,
            Decimal("100.00"),
        )

        self.assertTrue(
            self.order.delivery_paid_by_customer_on_receipt,
        )

    # Проверяем данные страницы заказа:
    # в контекст передаётся коллекция платежей,
    # даже если у заказа пока только один платёж.
    def test_manager_order_detail_contains_payments_in_context(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                args=[self.order.id],
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertIn(
            "payments",
            response.context,
        )

        self.assertEqual(
            list(response.context["payments"]),
            [self.payment],
        )

    # Проверяем, что менеджер может отметить оплату
    # как успешно оплаченную.
    def test_manager_can_mark_payment_as_paid(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                "orders:manager_mark_payment_paid",
                args=[self.order.id],
            ),
            data={
                "payment_id": self.payment.pk,
                "manager_comment": "Invoice paid.",
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_manager_order_detail_url(),
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PAID,
        )

        self.assertEqual(
            self.payment.manager_comment,
            "Invoice paid.",
        )

    # Проверяем, что менеджер может отменить оплату.
    def test_manager_can_mark_payment_as_cancelled(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                "orders:manager_mark_payment_cancelled",
                args=[self.order.id],
            ),
            data={
                "payment_id": self.payment.pk,
                "manager_comment": "Payment cancelled.",
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_manager_order_detail_url(),
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.CANCELLED,
        )

        self.assertEqual(
            self.payment.manager_comment,
            "Payment cancelled.",
        )

    # Проверяем, что администратор тоже может отметить оплату
    # как успешно оплаченную.
    def test_admin_can_mark_payment_as_paid(self):
        self.client.force_login(self.admin)

        response = self.client.post(
            reverse(
                "orders:manager_mark_payment_paid",
                args=[self.order.id],
            ),
            data={
                "payment_id": self.payment.pk,
                "manager_comment": "Admin confirmed payment.",
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_manager_order_detail_url(),
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PAID,
        )

        self.assertEqual(
            self.payment.manager_comment,
            "Admin confirmed payment.",
        )

    # Проверяем, что клиент не может изменять статус оплаты.
    def test_client_cannot_mark_payment_as_paid(self):
        self.client.force_login(self.client_user)

        response = self.client.post(
            reverse(
                "orders:manager_mark_payment_paid",
                args=[self.order.id],
            ),
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PENDING,
        )

    # Проверяем, что администратор может вернуть
    # платеж из PAID в PENDING.
    def test_admin_can_reset_payment_to_pending(self):
        mark_payment_paid(
            payment=self.payment,
        )

        self.client.force_login(
            self.admin,
        )

        response = self.client.post(
            reverse(
                "orders:admin_reset_payment_to_pending",
                args=[self.order.id],
            ),
            data={
                "payment_id": self.payment.pk,
                "manager_comment": "Wrong payment.",
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_manager_order_detail_url(),
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PENDING,
        )

        self.assertEqual(
            self.payment.manager_comment,
            "Wrong payment.",
        )

    # Проверяем, что менеджер не может
    # вернуть платеж в PENDING.
    def test_manager_cannot_reset_payment_to_pending(self):
        mark_payment_paid(
            payment=self.payment,
        )

        self.client.force_login(
            self.manager,
        )

        response = self.client.post(
            reverse(
                "orders:admin_reset_payment_to_pending",
                args=[self.order.id],
            ),
        )

        self.assertEqual(
            response.status_code,
            403,
        )

        self.payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PAID,
        )

    # Проверяем список менеджера при нескольких платежах одного заказа:
    # заказ отображается один раз, а счётчик ожидающих счетов
    # считает заказы, а не отдельные платежи.
    def test_manager_order_list_counts_order_with_multiple_payments_once(self):
        create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("20.00"),
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            self.get_manager_order_list_url(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            response.context["orders"],
            [self.order],
        )
        self.assertEqual(
            response.context["waiting_invoices_count"],
            1,
        )

    # Проверяем отображение заказа с несколькими платежами:
    # список показывает способ оплаты и выпущенный счёт,
    # а заказ больше не считается ожидающим выставления счёта.
    def test_manager_order_list_shows_invoice_with_multiple_payments(self):
        self.payment.amount = Decimal("40.00")
        self.payment.save(update_fields=["amount"])

        create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("60.00"),
        )

        create_test_invoice(
            order=self.order,
            payment=self.payment,
            amount=self.order.total_price,
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            self.get_manager_order_list_url(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, PaymentMethod.INVOICE.label)
        self.assertContains(response, "Generated")
        self.assertEqual(
            response.context["waiting_invoices_count"],
            0,
        )

    # Проверяем карточку заказа менеджера:
    # оба платежа одного заказа отображаются отдельно,
    # со своими идентификаторами и суммами.
    def test_manager_order_detail_shows_all_payments(self):
        self.payment.amount = Decimal("40.00")
        self.payment.save(update_fields=["amount"])

        second_payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("60.00"),
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f"Payment #{self.payment.pk}",
        )
        self.assertContains(
            response,
            f"Payment #{second_payment.pk}",
        )
        self.assertContains(response, "40.00")
        self.assertContains(response, "60.00")

    # Проверяем счёт в карточке заказа менеджера:
    # при двух платежах отображается счёт на полную стоимость заказа,
    # уведомление о его выпуске и ссылка на PDF.
    def test_manager_order_detail_shows_invoice_with_multiple_payments(self):
        self.payment.amount = Decimal("40.00")
        self.payment.save(update_fields=["amount"])

        create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("60.00"),
        )

        invoice = create_test_invoice(
            order=self.order,
            payment=self.payment,
            amount=self.order.total_price,
        )

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        invoice_pdf_url = reverse(
            "payments:manager_invoice_pdf",
            args=[invoice.pk],
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["invoice"], invoice)
        self.assertContains(response, invoice.invoice_number)
        self.assertContains(
            response,
            f'href="{invoice_pdf_url}"',
        )
        self.assertContains(response, "Invoice generated")

    # Проверяем подтверждение конкретного платежа:
    # менеджер переводит выбранный платёж в PAID,
    # а другой платёж того же заказа остаётся PENDING.
    def test_manager_marks_selected_payment_paid(self):
        self.payment.amount = Decimal("40.00")
        self.payment.save(update_fields=["amount"])

        selected_payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("60.00"),
        )

        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                "orders:manager_mark_payment_paid",
                kwargs={"pk": self.order.pk},
            ),
            data={
                "payment_id": selected_payment.pk,
                "manager_comment": "Second partial payment received.",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.payment.refresh_from_db()
        selected_payment.refresh_from_db()

        self.assertEqual(
            selected_payment.status,
            PaymentStatus.PAID,
        )
        self.assertEqual(
            self.payment.status,
            PaymentStatus.PENDING,
        )

    # Проверяем принадлежность платежа заказу:
    # нельзя подтвердить платёж другого заказа через текущий заказ.
    # Сервер возвращает 404, оба платежа остаются без изменений.
    def test_manager_cannot_mark_payment_from_another_order_paid(self):
        other_order = create_test_order(
            user=self.client_user,
            total_price=Decimal("70.00"),
            status=OrderStatus.PROCESSING,
        )

        foreign_payment = create_test_payment(
            order=other_order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("70.00"),
        )

        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                "orders:manager_mark_payment_paid",
                kwargs={"pk": self.order.pk},
            ),
            data={
                "payment_id": foreign_payment.pk,
            },
        )

        self.assertEqual(response.status_code, 404)

        self.payment.refresh_from_db()
        foreign_payment.refresh_from_db()

        self.assertEqual(
            self.payment.status,
            PaymentStatus.PENDING,
        )
        self.assertEqual(
            foreign_payment.status,
            PaymentStatus.PENDING,
        )

    # Проверяем отмену выбранного ожидающего платежа:
    # только он получает статус CANCELLED.
    # Другой платёж и статус заказа остаются без изменений.
    def test_manager_marks_selected_payment_cancelled(self):
        self.payment.amount = Decimal("40.00")
        self.payment.save(update_fields=["amount"])

        selected_payment = create_test_payment(
            order=self.order,
            method=PaymentMethod.INVOICE,
            amount=Decimal("60.00"),
        )

        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                "orders:manager_mark_payment_cancelled",
                kwargs={"pk": self.order.pk},
            ),
            data={
                "payment_id": selected_payment.pk,
                "manager_comment": "Payment cancelled.",
            },
        )

        self.assertEqual(response.status_code, 302)

        self.payment.refresh_from_db()
        selected_payment.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(
            selected_payment.status,
            PaymentStatus.CANCELLED,
        )
        self.assertEqual(
            self.payment.status,
            PaymentStatus.PENDING,
        )
        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )

    # После перевыпуска карточка менеджера показывает действующий Invoice.
    # Аннулированный документ сохраняется, а Payment для показа не требуется.
    def test_manager_order_detail_shows_current_invoice_after_reissue(self):
        account = create_personal_customer_account(
            user=self.client_user,
        )
        order = create_test_order(
            user=self.client_user,
            customer_account=account,
            status=OrderStatus.PROCESSING,
            payment_method=PaymentMethod.INVOICE,
        )

        create_test_invoice(
            order=order,
            payment=None,
            invoice_number="INV-2026-000001",
            status=InvoiceStatus.CANCELLED,
        )
        current_invoice = create_test_invoice(
            order=order,
            payment=None,
            invoice_number="INV-2026-000002",
            status=InvoiceStatus.ISSUED,
        )

        self.client.force_login(self.manager)
        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": order.pk},
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["invoice"], current_invoice)
        self.assertTrue(response.context["invoice_required"])
        self.assertContains(response, current_invoice.invoice_number)
        self.assertFalse(order.payments.exists())

    # После аннулирования Invoice заказ снова ожидает выставления счёта.
    # Сохранённый в истории документ не должен считаться действующим.
    def test_manager_order_list_waits_for_invoice_after_cancellation(self):
        self.order.payment_method = PaymentMethod.INVOICE
        self.order.save(update_fields=["payment_method"])

        create_test_invoice(
            order=self.order,
            payment=None,
            status=InvoiceStatus.CANCELLED,
        )

        self.client.force_login(self.manager)
        response = self.client.get(
            self.get_manager_order_list_url(),
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["waiting_invoices_count"],
            1,
        )
        self.assertContains(response, "Waiting")
        self.assertNotContains(response, "Generated")

    # Выбранный способ оплаты отображается ещё до поступления денег.
    # Заказ без Payment должен показывать By invoice и ожидание счёта.
    def test_manager_order_list_shows_invoice_method_without_payments(self):
        account = create_personal_customer_account(
            user=self.client_user,
        )
        order = create_test_order(
            user=self.client_user,
            customer_account=account,
            status=OrderStatus.NEW,
            payment_method=PaymentMethod.INVOICE,
        )

        self.client.force_login(self.manager)
        response = self.client.get(
            self.get_manager_order_list_url(),
            {"status": OrderStatus.NEW},
        )

        self.assertEqual(response.status_code, 200)
        self.assertCountEqual(
            response.context["orders"],
            [order],
        )
        self.assertContains(response, PaymentMethod.INVOICE.label)
        self.assertContains(response, "Waiting")
        self.assertFalse(order.payments.exists())

    # Форма завершения заказа запрашивает подтверждение полной отгрузки
    # и предупреждает, что отменить её на сайте будет нельзя.
    def test_manager_detail_requires_shipment_confirmation(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            )
        )

        confirmation_message = (
            f"Confirm full shipment of order #{self.order.pk}? "
            "Once confirmed, shipment cannot be cancelled "
            "and order items cannot be edited on the website."
        )
        expected_handler = (
            f"return confirm('{confirmation_message}');"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            f'onsubmit="{expected_handler}"',
        )

    # Подтверждение завершения через сайт создаёт полную отгрузку
    # и обязательство, затем возвращает менеджера в карточку заказа
    # с сохранением ссылки на исходный список.
    def test_manager_completes_order_with_shipment_from_frontend(self):
        self.client.force_login(self.manager)

        response = self.client.post(
            reverse(
                "orders:manager_order_status_update",
                kwargs={"pk": self.order.pk},
            ),
            {
                "status": OrderStatus.COMPLETED,
                "next": self.get_manager_order_list_url(),
            },
        )

        self.assertRedirects(
            response,
            self.get_expected_manager_order_detail_url(),
        )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.COMPLETED,
        )
        self.assertEqual(self.order.shipments.count(), 1)

        shipment = self.order.shipments.get()

        self.assertEqual(
            shipment.total_amount,
            Decimal("100.00"),
        )
        self.assertEqual(
            shipment.created_by_id,
            self.manager.pk,
        )
        self.assertEqual(shipment.items.count(), 1)
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("100.00"),
        )
        self.assertEqual(self.account.transactions.count(), 1)

    # Клиент не может подтвердить отгрузку прямым POST-запросом.
    # Сервер возвращает 403 и не меняет заказ или финансовые данные.
    def test_customer_cannot_complete_order_from_frontend(self):
        self.client.force_login(self.client_user)

        response = self.client.post(
            reverse(
                "orders:manager_order_status_update",
                kwargs={"pk": self.order.pk},
            ),
            {
                "status": OrderStatus.COMPLETED,
            },
        )

        self.assertEqual(response.status_code, 403)

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.status,
            OrderStatus.PROCESSING,
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertFalse(self.order.shipments.exists())
        self.assertFalse(self.account.transactions.exists())
