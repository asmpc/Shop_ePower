from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse
from django.utils.html import escape

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
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import InvoiceStatus
from shop_epower.payments.tests.helpers import create_test_invoice
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)


class TestsManagerOrderItemQuantityViews(TestCase):
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

        self.supplier = create_test_supplier(
            name="Own warehouse",
            is_own=True,
        )
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
            "orders:manager_reduce_order_item",
            kwargs={"pk": self.order_item.pk},
        )

    # Прямое открытие адреса изменения количества возвращает в заказ.
    # Параметры исходного списка сохраняются.
    # GET сохраняет заказ, резервы, остатки, балансы и историю.
    def test_quantity_get_redirects_to_order_without_changing_data(self):
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
        self.order_item.refresh_from_db()
        self.reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))
        self.assertEqual(self.reservation.quantity, 7)
        self.assertEqual(self.supplier_product.stock_quantity, 0)
        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertFalse(self.account.transactions.exists())
        self.assertFalse(self.order.item_changes.exists())

    # Страница заказа содержит встроенную форму выбранной позиции.
    # Для семи единиц допустимо новое количество от 1 до 6.
    # Причина обязательна, поля и CSRF-токен присутствуют на странице.
    def test_quantity_form_contains_required_fields_and_limits(self):
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
        form = item_row["quantity_form"]

        self.assertIsNotNone(form)
        self.assertEqual(
            set(form.fields),
            {"new_quantity", "reason"},
        )
        self.assertTrue(form.fields["new_quantity"].required)
        self.assertEqual(form.fields["new_quantity"].min_value, 1)
        self.assertEqual(form.fields["new_quantity"].max_value, 6)
        self.assertTrue(form.fields["reason"].required)

        self.assertContains(response, 'name="new_quantity"')
        self.assertContains(response, 'name="reason"')
        self.assertContains(response, 'min="1"')
        self.assertContains(response, 'max="6"')
        self.assertContains(response, 'method="post"')
        self.assertContains(response, 'name="csrfmiddlewaretoken"')

    # Менеджер отправляет новое количество и причину.
    # Позиция, итог и резерв уменьшаются, товар возвращается на склад.
    # История сохраняет сотрудника и причину; ответ возвращает в заказ.
    def test_manager_can_reduce_quantity_via_post(self):
        self.client.force_login(self.manager)
        reason = "Customer requested two fewer units."

        response = self.client.post(
            self.url,
            {
                "new_quantity": 5,
                "reason": reason,
            },
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

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("500.00"))
        self.assertEqual(self.order_item.quantity, 5)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("500.00"))
        self.assertEqual(self.reservation.quantity, 5)
        self.assertEqual(self.supplier_product.stock_quantity, 2)

        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertFalse(self.account.transactions.exists())

        change = self.order.item_changes.get()
        self.assertEqual(change.change_type, OrderItemChangeType.REDUCED)
        self.assertEqual(
            change.order_item_id_snapshot,
            self.order_item.pk,
        )
        self.assertEqual(change.changed_by, self.manager)
        self.assertEqual(change.reason, reason)
        self.assertEqual(change.old_quantity, 7)
        self.assertEqual(change.new_quantity, 5)
        self.assertEqual(change.old_order_total, Decimal("700.00"))
        self.assertEqual(change.new_order_total, Decimal("500.00"))

    # Без причины изменение запрещено.
    # Форма показывает ошибку и сохраняет введённое количество.
    # Заказ, резервы, остатки, балансы и история остаются прежними.
    # Без причины изменение отклоняется на странице заказа.
    # Форма остаётся раскрытой с введённым количеством и ошибкой.
    # Фильтр списка и все данные заказа сохраняются.
    def test_blank_reason_preserves_form_and_does_not_change_order(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("orders:manager_order_list")
            + "?status=processing&page=3"
        )
        panel_id = f"item-quantity-form-{self.order_item.pk}"

        response = self.client.post(
            self.url,
            {
                "new_quantity": 5,
                "reason": "   ",
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

        self.assertTrue(form.is_bound)
        self.assertEqual(form["new_quantity"].value(), "5")
        self.assertEqual(
            form.errors.as_data()["reason"][0].code,
            "required",
        )
        self.assertContains(
            response,
            form.errors["reason"][0],
        )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))
        self.assertEqual(self.reservation.quantity, 7)
        self.assertEqual(self.supplier_product.stock_quantity, 0)

        self.assertEqual(self.account.available_balance, Decimal("0.00"))
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))
        self.assertFalse(self.account.transactions.exists())
        self.assertFalse(self.order.item_changes.exists())

    # Действующий Invoice запрещает изменение состава заказа.
    # Ошибка сервиса отображается в форме, введённые данные сохраняются.
    # Заказ, счёт, резервы и остатки остаются прежними.
    def test_issued_invoice_blocks_change_and_preserves_form_data(self):
        invoice = create_test_invoice(
            order=self.order,
            payment=None,
            amount=self.order.total_price,
            status=InvoiceStatus.ISSUED,
        )
        self.client.force_login(self.manager)
        reason = "Customer requested two fewer units."

        response = self.client.post(
            self.url,
            {
                "new_quantity": 5,
                "reason": reason,
            },
        )

        self.assertEqual(response.status_code, 200)

        form = response.context["form"]
        error = "Cancel the issued invoice before changing order items."

        self.assertFormError(form, None, error)
        self.assertContains(response, error)
        self.assertEqual(form["new_quantity"].value(), "5")
        self.assertEqual(form["reason"].value(), reason)

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()
        invoice.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))
        self.assertEqual(self.reservation.quantity, 7)
        self.assertEqual(self.supplier_product.stock_quantity, 0)
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.amount, Decimal("700.00"))
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Клиент не может открыть форму сотрудника или отправить изменение.
    # Владение заказом не даёт таких прав.
    # Оба запроса отклоняются, данные заказа остаются прежними.
    def test_customer_cannot_open_form_or_reduce_quantity(self):
        self.client.force_login(self.user)

        get_response = self.client.get(self.url)

        self.assertEqual(get_response.status_code, 403)

        post_response = self.client.post(
            self.url,
            {
                "new_quantity": 5,
                "reason": "Customer attempts to change the order.",
            },
        )

        self.assertEqual(post_response.status_code, 403)

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.reservation.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))
        self.assertEqual(self.reservation.quantity, 7)
        self.assertEqual(self.supplier_product.stock_quantity, 0)
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Администратору доступна встроенная форма изменения количества.
    # После сохранения история содержит администратора как автора.
    def test_admin_can_reduce_quantity_and_is_recorded_as_author(self):
        admin = create_test_admin()
        self.client.force_login(admin)
        reason = "Quantity change agreed with the customer."

        form_response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )

        self.assertEqual(form_response.status_code, 200)
        self.assertContains(
            form_response,
            f'action="{self.url}"',
        )

        response = self.client.post(
            self.url,
            {
                "new_quantity": 5,
                "reason": reason,
            },
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("500.00"))
        self.assertEqual(self.order_item.quantity, 5)
        self.assertEqual(self.order_item.total_price, Decimal("500.00"))

        change = self.order.item_changes.get()

        self.assertEqual(change.changed_by, admin)
        self.assertEqual(change.reason, reason)
        self.assertEqual(change.change_type, OrderItemChangeType.REDUCED)
        self.assertEqual(change.old_quantity, 7)
        self.assertEqual(change.new_quantity, 5)

    # Форма сохраняет фильтр и страницу исходного списка.
    # После изменения возвращаемся в заказ, где ссылка «Назад»
    # ведёт в тот же список с прежними параметрами.
    def test_quantity_change_preserves_order_list_filters_and_page(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("orders:manager_order_list")
            + "?status=processing&page=3"
        )
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )
        expected_detail_url = (
            f"{detail_url}?{urlencode({'next': list_url})}"
        )

        form_response = self.client.get(
            detail_url,
            {"next": list_url},
        )

        self.assertEqual(form_response.status_code, 200)
        self.assertEqual(
            form_response.context["back_url"],
            list_url,
        )
        self.assertContains(
            form_response,
            (
                '<input type="hidden" name="next" '
                f'value="{escape(list_url)}">'
            ),
            html=True,
        )

        response = self.client.post(
            self.url,
            {
                "new_quantity": 5,
                "reason": "Quantity change agreed with the customer.",
                "next": list_url,
            },
            follow=True,
        )

        self.assertRedirects(response, expected_detail_url)
        self.assertEqual(response.context["back_url"], list_url)
        self.assertContains(
            response,
            f'href="{escape(list_url)}"',
        )

    # Недопустимое количество отклоняется проверкой формы.
    # Введённые данные и сообщение об ошибке сохраняются на странице.
    # Заказ, резервы и остатки не изменяются.
    def test_invalid_quantity_does_not_change_order(self):
        self.client.force_login(self.manager)
        reason = "Quantity change agreed with the customer."

        for new_quantity, error_code in (
            ("0", "min_value"),
            ("2.5", "invalid"),
            ("7", "max_value"),
            ("8", "max_value"),
        ):
            with self.subTest(new_quantity=new_quantity):
                response = self.client.post(
                    self.url,
                    {
                        "new_quantity": new_quantity,
                        "reason": reason,
                    },
                )

                self.assertEqual(response.status_code, 200)

                form = response.context["form"]

                self.assertTrue(
                    form.has_error(
                        "new_quantity",
                        code=error_code,
                    ),
                )
                self.assertEqual(
                    form["new_quantity"].value(),
                    new_quantity,
                )
                self.assertEqual(form["reason"].value(), reason)
                self.assertContains(
                    response,
                    form.errors["new_quantity"][0],
                )

                self.order.refresh_from_db()
                self.order_item.refresh_from_db()
                self.reservation.refresh_from_db()
                self.supplier_product.refresh_from_db()

                self.assertEqual(
                    self.order.total_price,
                    Decimal("700.00"),
                )
                self.assertEqual(self.order_item.quantity, 7)
                self.assertEqual(
                    self.order_item.total_price,
                    Decimal("700.00"),
                )
                self.assertEqual(self.reservation.quantity, 7)
                self.assertEqual(
                    self.supplier_product.stock_quantity,
                    0,
                )
                self.assertFalse(self.order.item_changes.exists())
                self.assertFalse(self.account.transactions.exists())

    # Изменение количества доступно прямо в карточке позиции.
    # Кнопка раскрывает изначально свёрнутую форму.
    # Форма отправляет данные обработчику выбранной позиции.
    def test_order_detail_contains_collapsed_quantity_form(self):
        self.client.force_login(self.manager)

        list_url = (
            reverse("orders:manager_order_list")
            + "?status=processing&page=3"
        )
        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )
        panel_id = f"item-quantity-form-{self.order_item.pk}"

        response = self.client.get(
            detail_url,
            {"next": list_url},
        )

        self.assertEqual(response.status_code, 200)
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
            f'action="{self.url}"',
        )
        self.assertContains(response, 'name="new_quantity"')
        self.assertContains(response, 'name="reason"')
        self.assertNotContains(
            response,
            f'href="{self.url}?',
        )

    # При действующем Invoice кнопка уменьшения количества остаётся видимой.
    # Она раскрывает пояснение о необходимости сначала аннулировать счёт.
    # Форма изменения количества недоступна, Invoice остаётся действующим.
    def test_issued_invoice_shows_quantity_action_with_explanation(self):
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

        panel_id = (
            f"item-editing-invoice-notice-{self.order_item.pk}"
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, invoice.invoice_number)
        self.assertContains(response, "Reduce quantity...")
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
            "Cancel the issued invoice before changing order items.",
        )
        self.assertNotContains(response, 'name="new_quantity"')
        self.assertNotContains(
            response,
            f'action="{self.url}"',
        )

        invoice.refresh_from_db()

        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)