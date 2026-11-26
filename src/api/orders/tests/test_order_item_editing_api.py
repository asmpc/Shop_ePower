from copy import deepcopy
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from shop_epower.accounts.models import PriceCategory
from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import (
    OrderItem,
    OrderItemChangeType,
    OrderStatus,
    OrderStockReservation,
)
from shop_epower.orders.services import complete_order_shipment
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import InvoiceStatus
from shop_epower.payments.tests.helpers import create_test_invoice
from shop_epower.suppliers.models import GlobalMarkup
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)


class TestsManagerOrderItemEditingAPI(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(user=self.user)

        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("700.00"),
        )
        self.product = create_test_product(
            base_price=Decimal("100.00"),
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=7,
            total_price=Decimal("700.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

        self.supplier = create_test_supplier(is_own=True)
        self.supplier_product = create_test_supplier_product(
            supplier=self.supplier,
            product=self.product,
            supplier_price=Decimal("100.00"),
            stock_quantity=0,
        )
        self.reservation = OrderStockReservation.objects.create(
            order_item=self.order_item,
            supplier_product=self.supplier_product,
            quantity=7,
        )

        self.url = reverse(
            "api_orders:manage-reduce-order-item",
            kwargs={"item_id": self.order_item.pk},
        )
        self.removal_url = reverse(
            "api_orders:manage-remove-order-item",
            kwargs={"item_id": self.order_item.pk},
        )
        self.addition_url = reverse(
            "api_orders:manage-add-order-items",
            kwargs={"order_id": self.order.pk},
        )
        self.payload = {
            "new_quantity": 5,
            "reason": "Customer requested two fewer units.",
        }

    def _assert_order_unchanged(
        self,
        *,
        expected_status=OrderStatus.PROCESSING,
        expected_total=Decimal("700.00"),
        expected_stock=0,
    ):
        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(self.order.status, expected_status)
        self.assertEqual(self.order.total_price, expected_total)
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))
        self.assertEqual(self.reservation.quantity, 7)
        self.assertEqual(
            self.supplier_product.stock_quantity,
            expected_stock,
        )
        self.assertFalse(self.order.item_changes.exists())

    def _add_second_price_batch(self):
        remaining_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("130.00"),
            quantity=2,
            total_price=Decimal("260.00"),
            currency_snapshot=self.order.currency_snapshot,
        )
        remaining_reservation = OrderStockReservation.objects.create(
            order_item=remaining_item,
            supplier_product=self.supplier_product,
            quantity=2,
        )

        self.order.total_price += remaining_item.total_price
        self.order.save(update_fields=["total_price"])

        return remaining_item, remaining_reservation

    def _prepare_addition_batch(self):
        GlobalMarkup.objects.create(
            percent=Decimal("30.00"),
        )

        self.supplier_product.currency = self.order.currency_snapshot
        self.supplier_product.stock_quantity = 5
        self.supplier_product.save(
            update_fields=["currency", "stock_quantity"],
        )

        self.addition_product = create_test_product(
            name="Second API product",
            manufacturer_article="SECOND-API-ADD-001",
            brand=self.product.brand,
            category=self.product.category,
            base_price=Decimal("200.00"),
        )
        self.addition_source = create_test_supplier_product(
            supplier=self.supplier,
            product=self.addition_product,
            supplier_article="SUP-SECOND-API-ADD-001",
            supplier_price=Decimal("200.00"),
            currency=self.order.currency_snapshot,
            stock_quantity=3,
        )

        return {
            "reason": "Customer requested additional products.",
            "items": [
                {
                    "product": self.product.pk,
                    "quantity": 2,
                    "confirmed_unit_price": "130.00",
                },
                {
                    "product": self.addition_product.pk,
                    "quantity": 1,
                    "confirmed_unit_price": "260.00",
                },
            ],
        }

    def _assert_addition_unchanged(
        self,
        *,
        expected_status=OrderStatus.PROCESSING,
    ):
        self._assert_order_unchanged(
            expected_status=expected_status,
            expected_stock=5,
        )
        self.addition_source.refresh_from_db()

        self.assertEqual(self.addition_source.stock_quantity, 3)
        self.assertEqual(self.order.items.count(), 1)

    # Менеджер уменьшает количество через API.
    # Ответ содержит обновлённый заказ; сумма и резерв уменьшаются,
    # товар возвращается на склад, история сохраняет автора и причину.
    def test_manager_can_reduce_order_item_quantity(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.order.pk)
        self.assertEqual(response.data["total_price"], "500.00")
        self.assertEqual(
            response.data["items"][0]["id"],
            self.order_item.pk,
        )
        self.assertEqual(response.data["items"][0]["quantity"], 5)

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("500.00"))
        self.assertEqual(self.order_item.quantity, 5)
        self.assertEqual(self.order_item.total_price, Decimal("500.00"))
        self.assertEqual(self.reservation.quantity, 5)
        self.assertEqual(self.supplier_product.stock_quantity, 2)

        change = self.order.item_changes.get()

        self.assertEqual(change.change_type, OrderItemChangeType.REDUCED)
        self.assertEqual(change.changed_by, self.manager)
        self.assertEqual(change.reason, self.payload["reason"])
        self.assertEqual(change.old_quantity, 7)
        self.assertEqual(change.new_quantity, 5)

    # Клиент не может уменьшить количество даже своего заказа.
    # Отказ сохраняет заказ, резервы, остатки и историю.
    def test_customer_cannot_reduce_own_order_item_quantity(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self._assert_order_unchanged()

    # Администратор может уменьшить количество через API.
    # История сохраняет администратора как автора изменения.
    def test_admin_can_reduce_quantity_and_is_recorded_as_author(self):
        admin = create_test_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)

        self.order_item.refresh_from_db()
        self.assertEqual(self.order_item.quantity, 5)

        change = self.order.item_changes.get()

        self.assertEqual(change.changed_by, admin)
        self.assertEqual(change.reason, self.payload["reason"])

    # Отсутствующая, пустая и пробельная причина запрещены.
    # API указывает ошибку поля reason и сохраняет исходное состояние.
    def test_reduction_requires_nonblank_reason(self):
        self.client.force_authenticate(user=self.manager)

        for reason_fields in (
            {},
            {"reason": ""},
            {"reason": "   "},
        ):
            with self.subTest(reason_fields=reason_fields):
                payload = {
                    "new_quantity": self.payload["new_quantity"],
                    **reason_fields,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("reason", response.data)
                self._assert_order_unchanged()

    # Нельзя установить ноль, оставить прежнее количество
    # или увеличить его через операцию уменьшения.
    # Каждый отказ сохраняет заказ, резерв, остаток и историю.
    def test_reduction_rejects_quantity_outside_allowed_range(self):
        self.client.force_authenticate(user=self.manager)

        for new_quantity in (0, 7, 8):
            with self.subTest(new_quantity=new_quantity):
                payload = {
                    **self.payload,
                    "new_quantity": new_quantity,
                }

                response = self.client.post(
                    self.url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self._assert_order_unchanged()

    # Уменьшение разрешено только для PROCESSING.
    # Во всех остальных статусах API возвращает отказ
    # и сохраняет данные заказа, резервы, остатки и историю.
    def test_reduction_requires_processing_order(self):
        self.client.force_authenticate(user=self.manager)

        for order_status in OrderStatus:
            if order_status == OrderStatus.PROCESSING:
                continue

            with self.subTest(status=order_status):
                self.order.status = order_status
                self.order.save(update_fields=["status"])

                response = self.client.post(
                    self.url,
                    self.payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self._assert_order_unchanged(
                    expected_status=order_status,
                )

    # Действующий Invoice блокирует изменение позиций через API.
    # Ответ объясняет необходимость аннулировать счёт.
    # Заказ, резервы, остатки, история и сам Invoice сохраняются.
    def test_issued_invoice_blocks_quantity_reduction(self):
        invoice = create_test_invoice(
            order=self.order,
            payment=None,
            amount=self.order.total_price,
            status=InvoiceStatus.ISSUED,
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Cancel the issued invoice before changing order items.",
            response.data["detail"],
        )
        self._assert_order_unchanged()

        invoice.refresh_from_db()

        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.amount, Decimal("700.00"))

    # Записанная отгрузка запрещает правку даже при PROCESSING.
    # Отказ API сохраняет заказ, снимок отгрузки и долг клиента.
    def test_recorded_shipment_blocks_reduction_even_in_processing(self):
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        # Возвращаем только метку статуса, чтобы проверить
        # запрет по факту отгрузки отдельно от запрета по статусу.
        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.url,
            self.payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Order items cannot be changed after shipment.",
            response.data["detail"],
        )
        self._assert_order_unchanged()

        self.account.refresh_from_db()
        shipment.refresh_from_db()

        self.assertEqual(self.order.shipments.count(), 1)
        self.assertEqual(shipment.total_amount, Decimal("700.00"))
        self.assertEqual(shipment.items.get().quantity, 7)
        self.assertEqual(self.account.debt_balance, Decimal("700.00"))
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(
            list(self.account.transactions.values_list("pk", flat=True)),
            [shipment.debt_transaction_id],
        )

    # Менеджер удаляет выбранную ценовую партию через API.
    # Её резерв освобождается, соседняя строка сохраняется.
    # Ответ и история отражают новый состав и сумму заказа.
    def test_manager_can_remove_selected_order_item(self):
        remaining_item, remaining_reservation = (
            self._add_second_price_batch()
        )
        removed_item_id = self.order_item.pk
        reason = "Customer requested removal of this price batch."

        self.client.force_authenticate(user=self.manager)
        url = reverse(
            "api_orders:manage-remove-order-item",
            kwargs={"item_id": removed_item_id},
        )

        response = self.client.post(
            url,
            {"reason": reason},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.order.pk)
        self.assertEqual(response.data["total_price"], "260.00")
        self.assertEqual(
            [
                (item["id"], item["quantity"])
                for item in response.data["items"]
            ],
            [(remaining_item.pk, 2)],
        )

        self.order.refresh_from_db()
        self.supplier_product.refresh_from_db()
        remaining_item.refresh_from_db()
        remaining_reservation.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("260.00"))
        self.assertEqual(self.supplier_product.stock_quantity, 7)
        self.assertEqual(remaining_item.quantity, 2)
        self.assertEqual(remaining_reservation.quantity, 2)
        self.assertFalse(
            OrderItem.objects.filter(pk=removed_item_id).exists(),
        )
        self.assertFalse(
            OrderStockReservation.objects.filter(
                order_item_id=removed_item_id,
            ).exists(),
        )

        change = self.order.item_changes.get()

        self.assertEqual(change.change_type, OrderItemChangeType.REMOVED)
        self.assertEqual(change.order_item_id_snapshot, removed_item_id)
        self.assertEqual(change.changed_by, self.manager)
        self.assertEqual(change.reason, reason)
        self.assertEqual(change.old_quantity, 7)
        self.assertEqual(change.new_quantity, 0)
        self.assertEqual(change.old_order_total, Decimal("960.00"))
        self.assertEqual(change.new_order_total, Decimal("260.00"))

    # Последнюю строку нельзя удалить даже при нескольких единицах.
    # Отказ сохраняет позицию, резерв, остаток, сумму и историю.
    def test_cannot_remove_last_order_line_even_with_multiple_units(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.removal_url,
            {"reason": "Customer requested removal of the final line."},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Cannot remove the last order item.",
            response.data["detail"],
        )
        self._assert_order_unchanged()
        self.assertEqual(self.order.items.count(), 1)

    # Клиент не может удалить строку собственного заказа.
    # В заказе две строки; отказ вызван ограничением роли.
    # Обе строки, сумма, резервы, остатки и история сохраняются.
    def test_customer_cannot_remove_own_order_item(self):
        self._add_second_price_batch()
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.removal_url,
            {"reason": "Customer attempts to remove an order item."},
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self._assert_order_unchanged(
            expected_total=Decimal("960.00"),
        )
        self.assertEqual(self.order.items.count(), 2)

    # Администратор может удалить выбранную строку заказа.
    # История сохраняет администратора как автора удаления.
    def test_admin_can_remove_item_and_is_recorded_as_author(self):
        self._add_second_price_batch()
        removed_item_id = self.order_item.pk
        admin = create_test_admin()
        reason = "Administrator confirmed removal of this price batch."

        self.client.force_authenticate(user=admin)

        response = self.client.post(
            self.removal_url,
            {"reason": reason},
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_price"], "260.00")
        self.assertFalse(
            OrderItem.objects.filter(pk=removed_item_id).exists(),
        )

        change = self.order.item_changes.get()

        self.assertEqual(change.change_type, OrderItemChangeType.REMOVED)
        self.assertEqual(change.order_item_id_snapshot, removed_item_id)
        self.assertEqual(change.changed_by, admin)
        self.assertEqual(change.reason, reason)

    # Удаление требует непустую причину.
    # Отсутствующее поле, пустая строка и пробелы отклоняются.
    # Обе позиции, сумма, резервы, остатки и история сохраняются.
    def test_removal_requires_nonblank_reason(self):
        self._add_second_price_batch()
        self.client.force_authenticate(user=self.manager)

        for payload in (
            {},
            {"reason": ""},
            {"reason": "   "},
        ):
            with self.subTest(payload=payload):
                response = self.client.post(
                    self.removal_url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("reason", response.data)
                self._assert_order_unchanged(
                    expected_total=Decimal("960.00"),
                )
                self.assertEqual(self.order.items.count(), 2)

    # Удаление разрешено только для PROCESSING.
    # В остальных статусах обе строки и исходные данные сохраняются.
    def test_removal_requires_processing_order(self):
        self._add_second_price_batch()
        self.client.force_authenticate(user=self.manager)

        for order_status in OrderStatus:
            if order_status == OrderStatus.PROCESSING:
                continue

            with self.subTest(status=order_status):
                self.order.status = order_status
                self.order.save(update_fields=["status"])

                response = self.client.post(
                    self.removal_url,
                    {"reason": "Customer requested removal of this batch."},
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(
                    "Order items can be changed only for processing orders.",
                    response.data["detail"],
                )
                self._assert_order_unchanged(
                    expected_status=order_status,
                    expected_total=Decimal("960.00"),
                )
                self.assertEqual(self.order.items.count(), 2)

    # Действующий Invoice запрещает удаление строки.
    # Заказ, резервы, остатки, история и сам счёт сохраняются.
    def test_issued_invoice_blocks_item_removal(self):
        self._add_second_price_batch()
        invoice = create_test_invoice(
            order=self.order,
            payment=None,
            amount=self.order.total_price,
            status=InvoiceStatus.ISSUED,
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.removal_url,
            {"reason": "Customer requested removal of this batch."},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Cancel the issued invoice before changing order items.",
            response.data["detail"],
        )
        self._assert_order_unchanged(
            expected_total=Decimal("960.00"),
        )
        self.assertEqual(self.order.items.count(), 2)

        invoice.refresh_from_db()

        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.amount, Decimal("960.00"))

    # Записанная отгрузка блокирует удаление даже при PROCESSING.
    # Обе строки, резервы, снимки отгрузки и долг сохраняются.
    def test_recorded_shipment_blocks_removal_even_in_processing(self):
        remaining_item, remaining_reservation = (
            self._add_second_price_batch()
        )
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        # Проверяем факт отгрузки независимо от метки статуса.
        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.removal_url,
            {"reason": "Customer requested removal of this batch."},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Order items cannot be changed after shipment.",
            response.data["detail"],
        )
        self._assert_order_unchanged(
            expected_total=Decimal("960.00"),
        )
        self.assertEqual(self.order.items.count(), 2)

        remaining_item.refresh_from_db()
        remaining_reservation.refresh_from_db()
        shipment.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(remaining_item.quantity, 2)
        self.assertEqual(remaining_reservation.quantity, 2)
        self.assertEqual(self.order.shipments.count(), 1)
        self.assertEqual(shipment.total_amount, Decimal("960.00"))
        self.assertCountEqual(
            shipment.items.values_list("order_item_id", "quantity"),
            [
                (self.order_item.pk, 7),
                (remaining_item.pk, 2),
            ],
        )
        self.assertEqual(self.account.debt_balance, Decimal("960.00"))
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(
            list(self.account.transactions.values_list("pk", flat=True)),
            [shipment.debt_transaction_id],
        )

    # Менеджер добавляет несколько позиций с одной общей причиной.
    # Новые строки получают актуальные цены и отдельные резервы.
    # Прежняя партия сохраняется; история записывает автора и причину.
    def test_manager_can_add_batch_with_one_shared_reason(self):
        payload = self._prepare_addition_batch()
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.addition_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], self.order.pk)
        self.assertEqual(response.data["total_price"], "1220.00")
        self.assertEqual(len(response.data["items"]), 3)

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()
        self.addition_source.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("1220.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.reservation.quantity, 7)
        self.assertEqual(self.supplier_product.stock_quantity, 3)
        self.assertEqual(self.addition_source.stock_quantity, 2)

        self.assertCountEqual(
            self.order.items.values_list(
                "product_id",
                "quantity",
                "unit_price",
            ),
            [
                (self.product.pk, 7, Decimal("100.00")),
                (self.product.pk, 2, Decimal("130.00")),
                (self.addition_product.pk, 1, Decimal("260.00")),
            ],
        )
        self.assertCountEqual(
            OrderStockReservation.objects.filter(
                order_item__order=self.order,
            ).values_list("quantity", flat=True),
            [7, 2, 1],
        )

        changes = list(self.order.item_changes.all())

        self.assertEqual(len(changes), 2)

        for change in changes:
            self.assertEqual(change.change_type, OrderItemChangeType.ADDED)
            self.assertEqual(change.changed_by, self.manager)
            self.assertEqual(change.reason, payload["reason"])

        self.assertFalse(self.account.transactions.exists())
        self.assertFalse(self.order.payments.exists())
        self.assertFalse(self.order.invoices.exists())

    # Клиент не может добавлять позиции даже в собственный заказ.
    # Отказ сохраняет исходный заказ, резервы, остатки и историю.
    def test_customer_cannot_add_batch_to_own_order(self):
        payload = self._prepare_addition_batch()
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            self.addition_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 403)
        self._assert_addition_unchanged()

    # Администратор может добавить набор позиций через API.
    # Каждая запись истории сохраняет администратора
    # и одну общую причину из запроса.
    def test_admin_can_add_batch_and_is_recorded_as_author(self):
        payload = self._prepare_addition_batch()
        admin = create_test_admin()
        self.client.force_authenticate(user=admin)

        response = self.client.post(
            self.addition_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_price"], "1220.00")
        self.assertEqual(len(response.data["items"]), 3)

        changes = list(self.order.item_changes.all())

        self.assertEqual(len(changes), 2)

        for change in changes:
            self.assertEqual(change.change_type, OrderItemChangeType.ADDED)
            self.assertEqual(change.changed_by, admin)
            self.assertEqual(change.reason, payload["reason"])

    # Список позиций обязателен и должен содержать хотя бы одну строку.
    # Отсутствующий или пустой items отклоняется без изменения заказа.
    def test_batch_addition_requires_nonempty_items(self):
        self.client.force_authenticate(user=self.manager)

        for item_fields in (
            {},
            {"items": []},
        ):
            with self.subTest(item_fields=item_fields):
                payload = {
                    "reason": "Customer requested additional products.",
                    **item_fields,
                }

                response = self.client.post(
                    self.addition_url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("items", response.data)
                self._assert_order_unchanged()
                self.assertEqual(self.order.items.count(), 1)

    # Нулевое, отрицательное и дробное количество запрещены.
    # Ошибка второй строки отклоняет весь запрос:
    # первая корректная строка также не сохраняется.
    def test_invalid_quantity_in_batch_rejects_entire_request(self):
        batch = self._prepare_addition_batch()
        self.client.force_authenticate(user=self.manager)

        for quantity in (0, -1, 1.5):
            with self.subTest(quantity=quantity):
                payload = deepcopy(batch)
                payload["items"][1]["quantity"] = quantity

                response = self.client.post(
                    self.addition_url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(
                    "quantity",
                    response.data["items"][1],
                )
                self._assert_addition_unchanged()

    # Нехватка товара во второй строке откатывает весь набор.
    # Первая обработанная строка, её резерв и история не сохраняются.
    # Заказ и остатки обоих товаров возвращаются к исходному состоянию.
    def test_stock_error_in_second_item_rolls_back_entire_batch(self):
        payload = self._prepare_addition_batch()
        payload["items"][1]["quantity"] = 4

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.addition_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            f"Not enough stock for product: {self.addition_product.name}",
            response.data["detail"],
        )
        self._assert_addition_unchanged()
        self.assertEqual(
            OrderStockReservation.objects.filter(
                order_item__order=self.order,
            ).count(),
            1,
        )
        self.assertFalse(self.account.transactions.exists())

    # Неактивный товар нельзя добавить в заказ.
    # Ошибка второй строки отклоняет весь набор без изменений.
    def test_inactive_product_in_batch_rejects_entire_request(self):
        payload = self._prepare_addition_batch()
        self.addition_product.is_active = False
        self.addition_product.save(update_fields=["is_active"])

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.addition_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("product", response.data["items"][1])
        self._assert_addition_unchanged()

        self.addition_product.refresh_from_db()
        self.assertFalse(self.addition_product.is_active)

    # Подтверждённая цена устарела после изменения цены поставщика.
    # Весь набор отклоняется, первая строка также откатывается.
    # Новая цена поставщика, сохранённая до запроса, остаётся.
    def test_stale_confirmed_price_rejects_entire_batch(self):
        payload = self._prepare_addition_batch()
        self.addition_source.supplier_price = Decimal("220.00")
        self.addition_source.save(update_fields=["supplier_price"])

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.addition_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Product price has changed. Confirm the current price again.",
            response.data["detail"],
        )
        self._assert_addition_unchanged()

        self.assertEqual(
            self.addition_source.supplier_price,
            Decimal("220.00"),
        )

    # Новые строки получают скидку владельца заказа — 10%.
    # У менеджера другая категория — 20%.
    # Прежняя партия сохраняет исходную цену 100.
    def test_batch_addition_uses_order_customer_price_category(self):
        payload = self._prepare_addition_batch()

        customer_category = PriceCategory.objects.create(
            name="Customer API discount",
            discount_percent=Decimal("10.00"),
        )
        manager_category = PriceCategory.objects.create(
            name="Manager API discount",
            discount_percent=Decimal("20.00"),
        )

        self.user.price_category = customer_category
        self.user.save(update_fields=["price_category"])

        self.manager.price_category = manager_category
        self.manager.save(update_fields=["price_category"])

        payload["items"][0]["confirmed_unit_price"] = "117.00"
        payload["items"][1]["confirmed_unit_price"] = "234.00"

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.addition_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["total_price"], "1168.00")

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()

        self.assertEqual(self.order.total_price, Decimal("1168.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertCountEqual(
            self.order.items.exclude(
                pk=self.order_item.pk,
            ).values_list("product_id", "quantity", "unit_price"),
            [
                (self.product.pk, 2, Decimal("117.00")),
                (self.addition_product.pk, 1, Decimal("234.00")),
            ],
        )

    # Добавление позиций разрешено только для PROCESSING.
    # В остальных статусах весь набор отклоняется:
    # заказ, резервы, остатки и история сохраняются.
    def test_batch_addition_requires_processing_order(self):
        payload = self._prepare_addition_batch()
        self.client.force_authenticate(user=self.manager)

        for order_status in OrderStatus:
            if order_status == OrderStatus.PROCESSING:
                continue

            with self.subTest(status=order_status):
                self.order.status = order_status
                self.order.save(update_fields=["status"])

                response = self.client.post(
                    self.addition_url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn(
                    "Order items can be changed only for processing orders.",
                    response.data["detail"],
                )
                self._assert_addition_unchanged(
                    expected_status=order_status,
                )

    # Действующий Invoice запрещает добавление позиций.
    # Заказ, резервы, остатки, история и сумма счёта сохраняются.
    def test_issued_invoice_blocks_batch_addition(self):
        payload = self._prepare_addition_batch()
        invoice = create_test_invoice(
            order=self.order,
            payment=None,
            amount=self.order.total_price,
            status=InvoiceStatus.ISSUED,
        )
        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.addition_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Cancel the issued invoice before changing order items.",
            response.data["detail"],
        )
        self._assert_addition_unchanged()

        invoice.refresh_from_db()

        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.amount, Decimal("700.00"))

    # Записанная отгрузка блокирует добавление даже при PROCESSING.
    # Заказ, остатки, резервы, снимок отгрузки и долг сохраняются.
    def test_recorded_shipment_blocks_batch_addition_even_in_processing(self):
        payload = self._prepare_addition_batch()
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        # Проверяем факт отгрузки независимо от метки статуса.
        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        self.client.force_authenticate(user=self.manager)

        response = self.client.post(
            self.addition_url,
            payload,
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(
            "Order items cannot be changed after shipment.",
            response.data["detail"],
        )
        self._assert_addition_unchanged()

        shipment.refresh_from_db()
        self.account.refresh_from_db()
        snapshot = shipment.items.get()

        self.assertEqual(self.order.shipments.count(), 1)
        self.assertEqual(shipment.total_amount, Decimal("700.00"))
        self.assertEqual(snapshot.order_item_id, self.order_item.pk)
        self.assertEqual(snapshot.quantity, 7)
        self.assertEqual(self.account.debt_balance, Decimal("700.00"))
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(
            list(self.account.transactions.values_list("pk", flat=True)),
            [shipment.debt_transaction_id],
        )

    # Общая причина набора обязательна.
    # Отсутствующая, пустая и пробельная причина отклоняются.
    # Ни одна позиция не добавляется, исходные данные сохраняются.
    def test_batch_addition_requires_one_nonblank_reason(self):
        batch = self._prepare_addition_batch()
        self.client.force_authenticate(user=self.manager)

        for reason_fields in (
            {},
            {"reason": ""},
            {"reason": "   "},
        ):
            with self.subTest(reason_fields=reason_fields):
                payload = {
                    "items": batch["items"],
                    **reason_fields,
                }

                response = self.client.post(
                    self.addition_url,
                    payload,
                    format="json",
                )

                self.assertEqual(response.status_code, 400)
                self.assertIn("reason", response.data)
                self._assert_addition_unchanged()
