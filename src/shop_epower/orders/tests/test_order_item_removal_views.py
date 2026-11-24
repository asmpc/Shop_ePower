from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

from shop_epower.accounts.tests.helpers import (
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
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import InvoiceStatus
from shop_epower.payments.tests.helpers import create_test_invoice
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)


class TestsManagerOrderItemRemovalViews(TestCase):
    def setUp(self):
        self.user = create_test_user()
        self.manager = create_test_manager()
        self.account = create_personal_customer_account(
            user=self.user,
        )
        self.order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("200.00"),
        )
        self.product = create_test_product(
            base_price=Decimal("100.00"),
        )

        self.remaining_item = self._create_order_item()
        self.order_item = self._create_order_item()

        self.url = reverse(
            "orders:manager_remove_order_item",
            kwargs={"pk": self.order_item.pk},
        )

        self.supplier = create_test_supplier()
        self.supplier_product = create_test_supplier_product(
            supplier=self.supplier,
            product=self.product,
            supplier_price=Decimal("100.00"),
            stock_quantity=0,
        )

        for item in (self.remaining_item, self.order_item):
            OrderStockReservation.objects.create(
                order_item=item,
                supplier_product=self.supplier_product,
                quantity=item.quantity,
            )

    def _create_order_item(self):
        return OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

    # Прямое открытие адреса удаления возвращает в заказ.
    # Параметры исходного списка сохраняются.
    # Обе строки, сумма заказа и история остаются прежними.
    def test_removal_get_redirects_to_order_without_changing_data(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("orders:manager_order_list")
            + "?status=processing&page=3"
        )
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )

        response = self.client.get(
            self.url,
            {"next": list_url},
        )

        self.assertRedirects(
            response,
            f"{detail_url}?{urlencode({'next': list_url})}",
            fetch_redirect_response=False,
        )

        self.order.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("200.00"))
        self.assertCountEqual(
            self.order.items.values_list("pk", "quantity"),
            [
                (self.order_item.pk, 1),
                (self.remaining_item.pk, 1),
            ],
        )
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Страница заказа содержит встроенную форму удаления выбранной строки.
    # Причина обязательна, подтверждение отправляется через POST.
    # На странице присутствуют CSRF-токен и поле возврата next.
    def test_removal_form_requires_reason_and_uses_post(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)

        item_row = next(
            row
            for row in response.context["order_item_rows"]
            if row["item"].pk == self.order_item.pk
        )
        form = item_row["removal_form"]

        self.assertIsNotNone(form)
        self.assertEqual(set(form.fields), {"reason"})
        self.assertTrue(form.fields["reason"].required)

        self.assertContains(response, 'name="reason"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')
        self.assertContains(response, 'name="next"')
        self.assertContains(response, 'type="submit"')
        self.assertContains(response, "Remove item")

    # Менеджер подтверждает удаление выбранной строки с причиной.
    # Другая строка и её резерв сохраняются, итог пересчитывается.
    # Товар возвращается на склад, история сохраняет автора и причину.
    def test_manager_can_remove_selected_item_via_post(self):
        self.client.force_login(self.manager)
        removed_item_id = self.order_item.pk
        remaining_reservation = (
            self.remaining_item.stock_reservations.get()
        )
        reason = "Customer requested removal of this item."

        response = self.client.post(
            self.url,
            {"reason": reason},
        )

        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )
        list_url = reverse("orders:manager_order_list")

        self.assertRedirects(
            response,
            f"{detail_url}?{urlencode({'next': list_url})}",
            fetch_redirect_response=False,
        )

        self.assertFalse(
            OrderItem.objects.filter(pk=removed_item_id).exists(),
        )
        self.assertFalse(
            OrderStockReservation.objects.filter(
                order_item_id=removed_item_id,
            ).exists(),
        )

        self.order.refresh_from_db()
        self.remaining_item.refresh_from_db()
        remaining_reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(
            list(self.order.items.values_list("pk", flat=True)),
            [self.remaining_item.pk],
        )
        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertEqual(self.remaining_item.quantity, 1)
        self.assertEqual(
            self.remaining_item.total_price,
            Decimal("100.00"),
        )
        self.assertEqual(remaining_reservation.quantity, 1)
        self.assertEqual(self.supplier_product.stock_quantity, 1)
        self.assertFalse(self.account.transactions.exists())

        change = self.order.item_changes.get()

        self.assertEqual(change.change_type, OrderItemChangeType.REMOVED)
        self.assertEqual(change.order_item_id_snapshot, removed_item_id)
        self.assertEqual(change.changed_by, self.manager)
        self.assertEqual(change.reason, reason)
        self.assertEqual(change.old_quantity, 1)
        self.assertEqual(change.new_quantity, 0)
        self.assertEqual(change.old_order_total, Decimal("200.00"))
        self.assertEqual(change.new_order_total, Decimal("100.00"))

    # После первого удаления оставшуюся строку удалить нельзя.
    # Отказ показывается в раскрытой форме внутри заказа.
    # Причина, параметры списка и состояние заказа сохраняются.
    def test_manager_cannot_remove_last_remaining_item(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("orders:manager_order_list")
            + "?status=processing&page=3"
        )
        panel_id = f"item-removal-form-{self.remaining_item.pk}"

        remaining_reservation = (
            self.remaining_item.stock_reservations.get()
        )

        first_response = self.client.post(
            self.url,
            {"reason": "Customer requested removal of the first item."},
        )

        self.assertEqual(first_response.status_code, 302)

        last_item_url = reverse(
            "orders:manager_remove_order_item",
            kwargs={"pk": self.remaining_item.pk},
        )
        reason = "Attempt to remove the last remaining item."

        response = self.client.post(
            last_item_url,
            {
                "reason": reason,
                "next": list_url,
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "orders/manage/order_detail.html",
        )
        self.assertEqual(response.context["order"].pk, self.order.pk)
        self.assertEqual(response.context["back_url"], list_url)
        self.assertContains(
            response,
            f'<div class="collapse show" id="{panel_id}">',
        )

        form = response.context["form"]
        error = "Cannot remove the last order item."

        self.assertFormError(form, None, error)
        self.assertContains(response, error)
        self.assertEqual(form["reason"].value(), reason)

        self.order.refresh_from_db()
        self.remaining_item.refresh_from_db()
        remaining_reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(
            list(self.order.items.values_list("pk", flat=True)),
            [self.remaining_item.pk],
        )
        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertEqual(self.remaining_item.quantity, 1)
        self.assertEqual(
            self.remaining_item.total_price,
            Decimal("100.00"),
        )
        self.assertEqual(remaining_reservation.quantity, 1)
        self.assertEqual(self.supplier_product.stock_quantity, 1)
        self.assertEqual(self.order.item_changes.count(), 1)
        self.assertFalse(self.account.transactions.exists())

    # Для каждой строки доступна свёрнутая форма удаления.
    # Кнопки раскрывают формы соответствующих позиций.
    # Каждая форма отправляется своему обработчику удаления.
    def test_order_detail_has_collapsed_removal_forms_for_each_item(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("orders:manager_order_list")
            + "?status=processing&page=3"
        )
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )

        response = self.client.get(
            detail_url,
            {"next": list_url},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["back_url"], list_url)

        for item in (self.remaining_item, self.order_item):
            removal_url = reverse(
                "orders:manager_remove_order_item",
                kwargs={"pk": item.pk},
            )
            panel_id = f"item-removal-form-{item.pk}"

            self.assertContains(
                response,
                f'data-bs-target="#{panel_id}"',
            )
            self.assertContains(
                response,
                f'<div class="collapse" id="{panel_id}">',
            )
            self.assertContains(
                response,
                f'action="{removal_url}"',
            )
            self.assertNotContains(
                response,
                f'href="{removal_url}?',
            )

            self.assertContains(
                response,
                f'id="id_item_{item.pk}_removal_reason"',
            )

        self.assertContains(
            response,
            (
                '<input type="hidden" name="next" '
                f'value="{escape(list_url)}">'
            ),
            html=True,
        )
        self.assertContains(response, "Remove item...", count=2)
        self.assertNotContains(response, "Reduce quantity")

    # При действующем Invoice кнопки удаления видны у обеих строк.
    # Каждая кнопка раскрывает пояснение под соответствующей позицией.
    # Формы удаления недоступны, счёт остаётся действующим.
    def test_issued_invoice_shows_removal_actions_with_explanation(self):
        invoice = create_test_invoice(
            order=self.order,
            payment=None,
            amount=self.order.total_price,
            status=InvoiceStatus.ISSUED,
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, invoice.invoice_number)
        self.assertContains(response, "Remove item...", count=2)
        self.assertContains(
            response,
            "Cancel the issued invoice before changing order items.",
        )

        for item in (self.remaining_item, self.order_item):
            panel_id = f"item-editing-invoice-notice-{item.pk}"
            removal_url = reverse(
                "orders:manager_remove_order_item",
                kwargs={"pk": item.pk},
            )

            self.assertContains(
                response,
                f'data-bs-target="#{panel_id}"',
            )
            self.assertContains(
                response,
                f'<div class="collapse" id="{panel_id}">',
            )
            self.assertNotContains(
                response,
                f'action="{removal_url}"',
            )

        invoice.refresh_from_db()

        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
