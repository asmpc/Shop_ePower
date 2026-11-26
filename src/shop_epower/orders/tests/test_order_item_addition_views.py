from decimal import Decimal
from urllib.parse import urlencode

from django.test import TestCase
from django.urls import reverse

from shop_epower.accounts.models import PriceCategory
from shop_epower.accounts.tests.helpers import (
    create_test_admin,
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import OrderItem, OrderStatus
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import InvoiceStatus
from shop_epower.payments.tests.helpers import create_test_invoice
from shop_epower.suppliers.models import GlobalMarkup
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)


class TestsManagerOrderItemAdditionViews(TestCase):
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
            total_price=Decimal("100.00"),
        )
        self.product = create_test_product(
            base_price=Decimal("100.00"),
        )
        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("100.00"),
            quantity=1,
            total_price=Decimal("100.00"),
            currency_snapshot=self.order.currency_snapshot,
        )

        self.supplier = create_test_supplier()
        self.supplier_product = create_test_supplier_product(
            supplier=self.supplier,
            product=self.product,
            supplier_price=Decimal("100.00"),
            currency=self.order.currency_snapshot,
            stock_quantity=5,
        )
        GlobalMarkup.objects.create(
            percent=Decimal("30.00"),
        )

        self.external_supplier = create_test_supplier(
            name="External supplier",
            is_own=False,
        )
        self.external_supplier_product = create_test_supplier_product(
            supplier=self.external_supplier,
            product=self.product,
            supplier_price=Decimal("100.00"),
            currency=self.order.currency_snapshot,
            stock_quantity=7,
            lead_time_days=3,
        )

    def _addition_batch_data(
        self,
        *,
        quantities=(2, 3),
        reason="Customer requested additional products.",
    ):
        """Возвращает данные набора с указанными количествами."""
        data = {
            "action": "confirm",
            "addition_items-TOTAL_FORMS": str(len(quantities)),
            "addition_items-INITIAL_FORMS": "0",
            "addition-reason": reason,
        }

        for index, quantity in enumerate(quantities):
            prefix = f"addition_items-{index}"
            data[f"{prefix}-product"] = self.product.pk
            data[f"{prefix}-quantity"] = str(quantity)
            data[f"{prefix}-confirmed_unit_price"] = "130.00"

        return data

    # Встроенный блок добавления изначально свёрнут.
    # Список выбранных товаров пуст, причина общая для всего набора.
    # Просмотр сохраняет состав, сумму заказа и финансовую историю.
    def test_order_detail_contains_collapsed_addition_form(self):
        self.client.force_login(self.manager)

        addition_url = reverse(
            "orders:manager_add_order_item",
            kwargs={"pk": self.order.pk},
        )
        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
        )
        panel_id = f"order-item-add-form-{self.order.pk}"

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add item...")
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
            f'action="{addition_url}#{panel_id}"',
        )

        form = response.context["add_item_form"]

        self.assertFalse(form.is_bound)
        self.assertEqual(
            set(form.fields),
            {"product", "quantity", "confirmed_unit_price"},
        )
        for field_name in form.fields:
            self.assertTrue(form.fields[field_name].required)

        self.assertEqual(form.fields["quantity"].min_value, 1)

        reason_form = response.context["addition_reason_form"]

        self.assertFalse(reason_form.is_bound)
        self.assertEqual(set(reason_form.fields), {"reason"})
        self.assertTrue(reason_form.fields["reason"].required)
        self.assertContains(
            response,
            'name="addition-reason"',
            count=1,
        )

        formset = response.context["addition_formset"]

        self.assertFalse(formset.is_bound)
        self.assertEqual(formset.total_form_count(), 0)
        self.assertNotIn("reason", formset.empty_form.fields)
        self.assertContains(
            response,
            'name="addition_items-TOTAL_FORMS"',
            count=1,
        )
        self.assertContains(response, "Add items")

        self.order.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # При действующем Invoice кнопка добавления остаётся видимой.
    # Вместо формы она раскрывает пояснение об аннулировании счёта.
    # Просмотр страницы не меняет состояние Invoice.
    def test_issued_invoice_shows_addition_action_with_explanation(self):
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
        panel_id = f"order-item-add-invoice-notice-{self.order.pk}"
        addition_url = reverse(
            "orders:manager_add_order_item",
            kwargs={"pk": self.order.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add item...")
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
        self.assertIsNone(response.context["add_item_form"])
        self.assertNotContains(
            response,
            f'action="{addition_url}#order-item-add-form-{self.order.pk}"',
        )

        invoice.refresh_from_db()

        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)

    # Поиск в форме добавления показывает подходящие активные товары.
    # После поиска панель остаётся раскрытой, запрос сохраняется.
    # Сам поиск не добавляет позиции и не создаёт финансовых операций.
    def test_product_search_filters_results_and_opens_addition_form(self):
        matching_product = create_test_product(
            name="Atlas Design Switch",
            manufacturer_article="ATLAS-ADD-001",
            brand=self.product.brand,
            category=self.product.category,
        )
        create_test_product(
            name="Atlas Hidden Switch",
            manufacturer_article="ATLAS-HIDDEN-001",
            brand=self.product.brand,
            category=self.product.category,
            is_active=False,
        )
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
            {"item_search": "Atlas"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            list(response.context["addition_products"]),
            [matching_product],
        )
        self.assertTrue(response.context["add_item_form_open"])
        self.assertContains(response, 'name="item_search"')
        self.assertContains(response, 'value="Atlas"')
        self.assertContains(response, matching_product.manufacturer_article)
        self.assertNotContains(response, "ATLAS-HIDDEN-001")
        self.assertContains(
            response,
            '<div class="collapse show" '
            f'id="order-item-add-form-{self.order.pk}">',
        )

        self.assertEqual(self.order.items.count(), 1)
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Выбор товара показывает актуальную цену для владельца заказа:
    # закупочная цена 100 + наценка 30% - скидка клиента 10% = 117.
    # Скидка менеджера не влияет на цену.
    # Предпросмотр сохраняет прежними товар, заказ, остатки и историю.
    def test_product_selection_previews_current_price_for_order_customer(self):
        customer_category = PriceCategory.objects.create(
            name="Customer discount",
            discount_percent=Decimal("10.00"),
        )
        manager_category = PriceCategory.objects.create(
            name="Manager discount",
            discount_percent=Decimal("20.00"),
        )
        self.user.price_category = customer_category
        self.user.save(update_fields=["price_category"])

        self.manager.price_category = manager_category
        self.manager.save(update_fields=["price_category"])

        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
            {"item_product": self.product.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context["addition_product"],
            self.product,
        )
        self.assertEqual(
            response.context["addition_unit_price"],
            Decimal("117.00"),
        )
        self.assertTrue(response.context["add_item_form_open"])

        form = response.context["add_item_form"]

        self.assertFalse(form.is_bound)
        self.assertEqual(form["product"].value(), self.product.pk)
        self.assertEqual(
            form["confirmed_unit_price"].value(),
            Decimal("117.00"),
        )
        self.assertContains(response, "Current unit price:")
        self.assertContains(response, "117.00")

        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("100.00"))
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.quantity, 1)
        self.assertEqual(self.supplier_product.stock_quantity, 5)
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # В результатах поиска менеджер видит доступное количество:
    # отдельно на собственном складе и под заказ у поставщиков.
    def test_product_search_displays_own_and_supplier_stock(self):
        self.client.force_login(self.manager)

        response = self.client.get(
            reverse(
                "orders:manager_order_detail",
                kwargs={"pk": self.order.pk},
            ),
            {"item_search": self.product.manufacturer_article},
        )

        self.assertEqual(response.status_code, 200)

        products = list(response.context["addition_products"])

        self.assertEqual(len(products), 1)
        self.assertEqual(products[0].pk, self.product.pk)
        self.assertEqual(products[0].inventory["own_stock"], 5)
        self.assertEqual(products[0].inventory["supplier_stock"], 7)

        content = response.content.decode()

        self.assertRegex(content, r"In stock:\s*5")
        self.assertRegex(content, r"Available to order:\s*7")

    # Менеджер сохраняет две новые строки одним запросом с общей причиной.
    # Прежняя позиция сохраняет свою цену, новые получают цену 130.
    # История содержит автора и общую причину для каждой новой строки.
    # Возврат сохраняет фильтр и страницу исходного списка заказов.
    def test_manager_can_add_batch_with_one_reason(self):
        self.client.force_login(self.manager)

        detail_url = reverse(
            "orders:manager_order_detail",
            kwargs={"pk": self.order.pk},
        )
        list_url = reverse("orders:manager_order_list")
        next_url = f"{list_url}?status=processing&page=2"

        data = self._addition_batch_data()
        data["next"] = next_url

        response = self.client.post(
            reverse(
                "orders:manager_add_order_item",
                kwargs={"pk": self.order.pk},
            ),
            data,
        )

        self.assertRedirects(
            response,
            f"{detail_url}?{urlencode({'next': next_url})}",
        )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 3)
        self.assertEqual(self.order.total_price, Decimal("750.00"))
        self.assertEqual(self.order_item.quantity, 1)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.supplier_product.stock_quantity, 0)

        new_items = (
            self.order.items
            .exclude(pk=self.order_item.pk)
            .order_by("pk")
        )
        self.assertEqual(
            list(new_items.values_list("quantity", "unit_price")),
            [
                (2, Decimal("130.00")),
                (3, Decimal("130.00")),
            ],
        )

        changes = self.order.item_changes.all()

        self.assertEqual(changes.count(), 2)
        for change in changes:
            self.assertEqual(change.reason, data["addition-reason"])
            self.assertEqual(change.changed_by, self.manager)

        self.assertFalse(self.account.transactions.exists())

    # Нехватка товара возвращает раскрытый блок добавления.
    # Обе строки и общая причина сохраняются для исправления.
    # Заказ, остатки и история остаются без изменений.
    def test_stock_error_preserves_batch_and_common_reason(self):
        self.client.force_login(self.manager)

        data = self._addition_batch_data()
        data["addition_items-1-quantity"] = "20"

        response = self.client.post(
            reverse(
                "orders:manager_add_order_item",
                kwargs={"pk": self.order.pk},
            ),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_item_form_open"])

        formset = response.context["addition_formset"]
        reason_form = response.context["addition_reason_form"]

        self.assertTrue(formset.is_bound)
        self.assertEqual(formset.total_form_count(), 2)
        self.assertEqual(formset.forms[0]["quantity"].value(), "2")
        self.assertEqual(formset.forms[1]["quantity"].value(), "20")
        self.assertEqual(
            reason_form["reason"].value(),
            data["addition-reason"],
        )
        self.assertFormError(
            reason_form,
            None,
            f"Not enough stock for product: {self.product.name}",
        )

        for index in range(2):
            for field_name in (
                "product",
                "quantity",
                "confirmed_unit_price",
            ):
                self.assertContains(
                    response,
                    f'name="addition_items-{index}-{field_name}"',
                )

        self.order.refresh_from_db()
        self.supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertEqual(self.supplier_product.stock_quantity, 5)
        self.assertEqual(self.external_supplier_product.stock_quantity, 7)
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Менеджер добавляет товар во временный список формы.
    # Общую причину пока можно не заполнять.
    # Заказ, цена товара, остатки и история остаются прежними.
    def test_manager_can_stage_item_without_common_reason(self):
        self.client.force_login(self.manager)

        data = self._addition_batch_data(
            quantities=(),
            reason="",
        )
        data.update(
            {
                "action": "stage",
                "product": self.product.pk,
                "quantity": "2",
                "confirmed_unit_price": "130.00",
            },
        )

        response = self.client.post(
            reverse(
                "orders:manager_add_order_item",
                kwargs={"pk": self.order.pk},
            ),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_item_form_open"])

        formset = response.context["addition_formset"]
        reason_form = response.context["addition_reason_form"]

        self.assertTrue(formset.is_bound)
        self.assertEqual(formset.total_form_count(), 1)
        self.assertTrue(formset.is_valid())

        item_data = formset.forms[0].cleaned_data

        self.assertEqual(item_data["product"], self.product)
        self.assertEqual(item_data["quantity"], 2)
        self.assertEqual(
            item_data["confirmed_unit_price"],
            Decimal("130.00"),
        )
        self.assertFalse(reason_form.errors)
        self.assertNotContains(response, "This field is required.")

        self.assertContains(
            response,
            (
                '<button type="submit" name="action" value="confirm" '
                'class="btn btn-primary btn-sm" formnovalidate>'
                'Add items</button>'
            ),
            html=True,
        )

        self.order.refresh_from_db()
        self.product.refresh_from_db()
        self.supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertEqual(self.product.base_price, Decimal("100.00"))
        self.assertEqual(self.supplier_product.stock_quantity, 5)
        self.assertEqual(self.external_supplier_product.stock_quantity, 7)
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Новый поиск сохраняет набранные позиции и общую причину.
    # Найденные товары отображаются отдельно от выбранного набора.
    # Поиск не изменяет заказ и не создаёт историю правок.
    def test_product_search_preserves_staged_items_and_common_reason(self):
        matching_product = create_test_product(
            name="Additional Socket",
            manufacturer_article="SOCKET-ADD-001",
            brand=self.product.brand,
            category=self.product.category,
        )
        self.client.force_login(self.manager)

        reason = "Customer requested additional electrical products."
        data = self._addition_batch_data(
            quantities=(2,),
            reason=reason,
        )
        data.update(
            {
                "action": "search",
                "item_search": "Socket",
            },
        )

        response = self.client.post(
            reverse(
                "orders:manager_add_order_item",
                kwargs={"pk": self.order.pk},
            ),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_item_form_open"])
        self.assertEqual(response.context["item_search"], "Socket")
        self.assertEqual(
            list(response.context["addition_products"]),
            [matching_product],
        )

        formset = response.context["addition_formset"]
        reason_form = response.context["addition_reason_form"]

        self.assertEqual(formset.total_form_count(), 1)
        self.assertTrue(formset.is_valid())
        self.assertEqual(
            formset.forms[0].cleaned_data["product"],
            self.product,
        )
        self.assertEqual(
            formset.forms[0].cleaned_data["quantity"],
            2,
        )
        self.assertEqual(reason_form["reason"].value(), reason)
        self.assertFalse(reason_form.errors)

        self.assertContains(response, 'value="Socket"')
        self.assertContains(response, matching_product.manufacturer_article)
        self.assertContains(
            response,
            'name="addition_items-0-quantity"',
        )

        self.order.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertEqual(self.supplier_product.stock_quantity, 5)
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Выбор товара сохраняет набранные строки и общую причину.
    # В предпросмотре видны актуальная цена, склад и количество под заказ.
    # Выбор товара не изменяет сам заказ.
    def test_product_selection_preserves_batch_and_displays_inventory(self):
        self.client.force_login(self.manager)

        reason = "Customer requested additional electrical products."
        data = self._addition_batch_data(
            quantities=(2,),
            reason=reason,
        )
        data.pop("action")
        data["item_product"] = self.product.pk

        response = self.client.post(
            reverse(
                "orders:manager_add_order_item",
                kwargs={"pk": self.order.pk},
            ),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_item_form_open"])

        product = response.context["addition_product"]

        self.assertEqual(product, self.product)
        self.assertEqual(
            response.context["addition_unit_price"],
            Decimal("130.00"),
        )
        self.assertEqual(product.inventory["own_stock"], 5)
        self.assertEqual(product.inventory["supplier_stock"], 7)

        formset = response.context["addition_formset"]
        reason_form = response.context["addition_reason_form"]

        self.assertEqual(formset.total_form_count(), 1)
        self.assertTrue(formset.is_valid())
        self.assertEqual(
            formset.forms[0].cleaned_data["quantity"],
            2,
        )
        self.assertEqual(reason_form["reason"].value(), reason)

        content = response.content.decode()

        self.assertRegex(content, r"In stock:\s*5")
        self.assertRegex(content, r"Available to order:\s*7")

        self.order.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertEqual(self.supplier_product.stock_quantity, 5)
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Менеджер исключает строку из временного списка добавления.
    # Остальные строки и общая причина сохраняются.
    # Сохранённый заказ и история правок не меняются.
    def test_manager_can_remove_item_from_staged_batch(self):
        self.client.force_login(self.manager)

        data = self._addition_batch_data()
        data.pop("action")
        data["remove_item"] = "0"

        response = self.client.post(
            reverse(
                "orders:manager_add_order_item",
                kwargs={"pk": self.order.pk},
            ),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_item_form_open"])

        formset = response.context["addition_formset"]
        reason_form = response.context["addition_reason_form"]

        self.assertTrue(formset.is_valid())
        self.assertEqual(formset.total_form_count(), 2)
        self.assertEqual(len(formset.deleted_forms), 1)
        self.assertTrue(formset.forms[0].cleaned_data["DELETE"])

        active_items = [
            form.cleaned_data
            for form in formset.forms
            if not form.cleaned_data.get("DELETE")
        ]

        self.assertEqual(len(active_items), 1)
        self.assertEqual(active_items[0]["product"], self.product)
        self.assertEqual(active_items[0]["quantity"], 3)
        self.assertEqual(
            reason_form["reason"].value(),
            data["addition-reason"],
        )

        self.assertContains(response, 'name="addition_items-0-DELETE"')
        self.assertNotContains(response, 'name="addition_items-0-quantity"')
        self.assertContains(response, 'name="addition_items-1-quantity"')
        self.assertContains(response, "Remove from list")

        self.order.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # После исключения строки сохраняется только оставшаяся позиция.
    # Исключённая строка передаёт только DELETE, без товара и количества.
    # История создаётся только для фактически добавленной позиции.
    def test_confirmation_skips_removed_staged_item(self):
        self.client.force_login(self.manager)

        data = self._addition_batch_data()
        data["addition_items-0-DELETE"] = "on"

        for field_name in (
            "product",
            "quantity",
            "confirmed_unit_price",
        ):
            data.pop(f"addition_items-0-{field_name}")

        response = self.client.post(
            reverse(
                "orders:manager_add_order_item",
                kwargs={"pk": self.order.pk},
            ),
            data,
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 2)
        self.assertEqual(self.order.total_price, Decimal("490.00"))
        self.assertEqual(self.order_item.quantity, 1)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))

        new_item = self.order.items.exclude(
            pk=self.order_item.pk,
        ).get()

        self.assertEqual(new_item.quantity, 3)
        self.assertEqual(new_item.unit_price, Decimal("130.00"))
        self.assertEqual(new_item.total_price, Decimal("390.00"))
        self.assertEqual(self.supplier_product.stock_quantity, 2)
        self.assertEqual(self.external_supplier_product.stock_quantity, 7)

        change = self.order.item_changes.get()

        self.assertEqual(change.order_item_id_snapshot, new_item.pk)
        self.assertEqual(change.reason, data["addition-reason"])
        self.assertEqual(change.changed_by, self.manager)
        self.assertFalse(self.account.transactions.exists())

    # При окончательном сохранении общая причина обязательна.
    # Пробелы не считаются заполненной причиной.
    # Ошибка сохраняет набранные строки без изменения заказа.
    def test_confirmation_requires_common_reason(self):
        self.client.force_login(self.manager)

        data = self._addition_batch_data(reason="   ")

        response = self.client.post(
            reverse(
                "orders:manager_add_order_item",
                kwargs={"pk": self.order.pk},
            ),
            data,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["add_item_form_open"])

        reason_form = response.context["addition_reason_form"]
        formset = response.context["addition_formset"]

        self.assertFormError(
            reason_form,
            "reason",
            "This field is required.",
        )
        self.assertTrue(formset.is_bound)
        self.assertEqual(formset.total_form_count(), 2)

        for index, quantity in enumerate((2, 3)):
            self.assertEqual(
                formset.forms[index]["quantity"].value(),
                str(quantity),
            )
            self.assertContains(
                response,
                f'name="addition_items-{index}-quantity"',
            )

        self.order.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertEqual(self.supplier_product.stock_quantity, 5)
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Клиент не может использовать служебный подбор и добавление товаров.
    # Владение заказом не даёт прав менеджера.
    # Запрещены поиск, добавление в список, сохранение и исключение строки.
    def test_customer_cannot_use_addition_actions(self):
        self.client.force_login(self.user)

        for action in ("search", "stage", "confirm", "remove"):
            with self.subTest(action=action):
                data = self._addition_batch_data()
                data.update(
                    {
                        "action": action,
                        "item_search": self.product.manufacturer_article,
                        "product": self.product.pk,
                        "quantity": "1",
                        "confirmed_unit_price": "130.00",
                    },
                )

                if action == "remove":
                    data.pop("action")
                    data["remove_item"] = "0"

                response = self.client.post(
                    reverse(
                        "orders:manager_add_order_item",
                        kwargs={"pk": self.order.pk},
                    ),
                    data,
                )

                self.assertEqual(response.status_code, 403)

        self.order.refresh_from_db()
        self.supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("100.00"))
        self.assertEqual(self.supplier_product.stock_quantity, 5)
        self.assertFalse(self.order.item_changes.exists())
        self.assertFalse(self.account.transactions.exists())

    # Администратор может сохранить набор с общей причиной.
    # В истории автором каждой новой позиции становится администратор.
    def test_admin_can_add_batch_with_one_reason(self):
        admin = create_test_admin()
        self.client.force_login(admin)

        data = self._addition_batch_data()

        response = self.client.post(
            reverse(
                "orders:manager_add_order_item",
                kwargs={"pk": self.order.pk},
            ),
            data,
        )

        self.assertEqual(response.status_code, 302)

        self.order.refresh_from_db()

        self.assertEqual(self.order.items.count(), 3)
        self.assertEqual(self.order.total_price, Decimal("750.00"))

        changes = self.order.item_changes.all()

        self.assertEqual(changes.count(), 2)
        for change in changes:
            self.assertEqual(change.changed_by, admin)
            self.assertEqual(change.reason, data["addition-reason"])
