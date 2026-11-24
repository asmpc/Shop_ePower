from decimal import Decimal
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop_epower.accounts.models import PriceCategory
from shop_epower.accounts.tests.helpers import (
    create_test_manager,
    create_test_user,
)
from shop_epower.catalog.tests.helpers import create_test_product
from shop_epower.finance.services import create_personal_customer_account
from shop_epower.orders.models import (
    OrderFundAssignmentSource,
    OrderItem,
    OrderItemChange,
    OrderItemChangeType,
    OrderStatus,
    OrderStockReservation,
)
from shop_epower.orders.selectors import get_order_financial_summary
from shop_epower.orders.services import (
    add_order_item,
    assign_order_funds,
    cancel_order_fund_assignment,
    complete_order_shipment,
    reduce_order_item_quantity,
    remove_order_item,
)
from shop_epower.orders.tests.helpers import create_test_order
from shop_epower.payments.models import (
    InvoiceStatus,
    PaymentMethod,
    PaymentStatus,
)
from shop_epower.payments.services import record_manual_order_payment
from shop_epower.payments.tests.helpers import create_test_invoice
from shop_epower.suppliers.models import GlobalMarkup
from shop_epower.suppliers.tests.helpers import (
    create_test_supplier,
    create_test_supplier_product,
)


class TestsOrderItemEditingServices(TestCase):
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

        self.own_supplier = create_test_supplier(
            name="Own warehouse",
            is_own=True,
        )
        self.external_supplier = create_test_supplier(
            name="External supplier",
            is_own=False,
        )

        self.own_supplier_product = create_test_supplier_product(
            supplier=self.own_supplier,
            product=self.product,
            stock_quantity=0,
        )
        self.external_supplier_product = create_test_supplier_product(
            supplier=self.external_supplier,
            product=self.product,
            stock_quantity=0,
            lead_time_days=3,
        )

        self.own_reservation = OrderStockReservation.objects.create(
            order_item=self.order_item,
            supplier_product=self.own_supplier_product,
            quantity=4,
        )
        self.external_reservation = OrderStockReservation.objects.create(
            order_item=self.order_item,
            supplier_product=self.external_supplier_product,
            quantity=3,
        )

    def _add_second_price_batch(self):
        """Добавляет вторую ценовую партию с отдельным резервом."""
        second_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=Decimal("130.00"),
            quantity=2,
            total_price=Decimal("260.00"),
            currency_snapshot=self.order.currency_snapshot,
        )
        reservation = OrderStockReservation.objects.create(
            order_item=second_item,
            supplier_product=self.own_supplier_product,
            quantity=2,
        )

        self.order.total_price += second_item.total_price
        self.order.save(update_fields=["total_price"])

        return second_item, reservation

    def _prepare_addition_sources(self):
        """Готовит источники для добавления пяти единиц по цене 130."""
        GlobalMarkup.objects.create(
            percent=Decimal("30.00"),
        )

        for source, available_quantity in (
            (self.own_supplier_product, 2),
            (self.external_supplier_product, 3),
        ):
            source.supplier_price = Decimal("100.00")
            source.currency = self.order.currency_snapshot
            source.stock_quantity = available_quantity
            source.save(
                update_fields=[
                    "supplier_price",
                    "currency",
                    "stock_quantity",
                ],
            )

    # Проверяем запрет удаления во всех статусах, кроме PROCESSING.
    # При отказе статус, строки, суммы и история сохраняются.
    def test_removal_requires_processing_order(self):
        self._add_second_price_batch()

        for status in OrderStatus.values:
            if status == OrderStatus.PROCESSING:
                continue

            with self.subTest(status=status):
                self.order.status = status
                self.order.save(update_fields=["status"])

                with self.assertRaisesMessage(
                    ValidationError,
                    "Order items can be changed only for processing orders.",
                ):
                    remove_order_item(
                        order_item=self.order_item,
                        changed_by=self.manager,
                        reason="Customer requested removal.",
                    )

                self.order.refresh_from_db()
                self.order_item.refresh_from_db()

                self.assertEqual(self.order.status, status)
                self.assertEqual(self.order.items.count(), 2)
                self.assertEqual(
                    self.order.total_price,
                    Decimal("960.00"),
                )
                self.assertEqual(self.order_item.quantity, 7)
                self.assertEqual(
                    self.order_item.total_price,
                    Decimal("700.00"),
                )
                self.assertFalse(self.order.item_changes.exists())

    # Проверяем запрет изменения состава заказа клиентом:
    # сервис отклоняет запрос, количество и суммы сохраняются.
    def test_customer_cannot_reduce_order_item_quantity(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Only managers and administrators can change order items.",
        ):
            reduce_order_item_quantity(
                order_item=self.order_item,
                new_quantity=5,
                changed_by=self.user,
                reason="Customer requested fewer items.",
            )

        self.order_item.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(
            self.order_item.total_price,
            Decimal("700.00"),
        )
        self.assertEqual(
            self.order.total_price,
            Decimal("700.00"),
        )

    # Проверяем запрет изменения нового заказа:
    # менеджер сначала должен взять его в работу.
    # При отказе статус, количество и суммы сохраняются.
    def test_manager_cannot_reduce_item_of_new_order(self):
        self.order.status = OrderStatus.NEW
        self.order.save(
            update_fields=["status"],
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Order items can be changed only for processing orders.",
        ):
            reduce_order_item_quantity(
                order_item=self.order_item,
                new_quantity=5,
                changed_by=self.manager,
                reason="Customer requested fewer items.",
            )

        self.order_item.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.order.status, OrderStatus.NEW)
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(
            self.order_item.total_price,
            Decimal("700.00"),
        )
        self.assertEqual(
            self.order.total_price,
            Decimal("700.00"),
        )

    # Проверяем запрет изменения при действующем Invoice:
    # менеджер сначала должен аннулировать счёт.
    # При отказе позиция, суммы и документ сохраняются.
    def test_cannot_reduce_item_with_issued_invoice(self):
        invoice = create_test_invoice(
            order=self.order,
            payment=None,
            amount=self.order.total_price,
            status=InvoiceStatus.ISSUED,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Cancel the issued invoice before changing order items.",
        ):
            reduce_order_item_quantity(
                order_item=self.order_item,
                new_quantity=5,
                changed_by=self.manager,
                reason="Customer requested fewer items.",
            )

        self.order_item.refresh_from_db()
        self.order.refresh_from_db()
        invoice.refresh_from_db()

        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(
            self.order_item.total_price,
            Decimal("700.00"),
        )
        self.assertEqual(
            self.order.total_price,
            Decimal("700.00"),
        )
        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.amount, Decimal("700.00"))

    # Проверяем обязательную причину изменения:
    # None, пустая строка и пробелы отклоняются.
    # Количество и суммы остаются без изменений.
    def test_reduction_requires_nonblank_reason(self):
        for reason in (None, "", "   "):
            with self.subTest(reason=reason):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Order item change reason is required.",
                ):
                    reduce_order_item_quantity(
                        order_item=self.order_item,
                        new_quantity=5,
                        changed_by=self.manager,
                        reason=reason,
                    )

        self.order_item.refresh_from_db()
        self.order.refresh_from_db()

        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(
            self.order_item.total_price,
            Decimal("700.00"),
        )
        self.assertEqual(
            self.order.total_price,
            Decimal("700.00"),
        )

    # Проверяем новое количество:
    # оно должно быть целым положительным числом,
    # строго меньшим текущего количества.
    # Каждый отказ сохраняет позицию и суммы.
    def test_reduction_requires_valid_smaller_quantity(self):
        for new_quantity in (
            None,
            True,
            "5",
            5.5,
            0,
            -1,
            7,
            8,
        ):
            with self.subTest(new_quantity=new_quantity):
                with self.assertRaisesMessage(
                    ValidationError,
                    "New quantity must be a positive integer "
                    "below the current quantity.",
                ):
                    reduce_order_item_quantity(
                        order_item=self.order_item,
                        new_quantity=new_quantity,
                        changed_by=self.manager,
                        reason="Customer requested fewer items.",
                    )

                self.order_item.refresh_from_db()
                self.order.refresh_from_db()

                self.assertEqual(self.order_item.quantity, 7)
                self.assertEqual(
                    self.order_item.total_price,
                    Decimal("700.00"),
                )
                self.assertEqual(
                    self.order.total_price,
                    Decimal("700.00"),
                )

    # Проверяем запрет изменения после записанной отгрузки:
    # даже при статусе PROCESSING факт отгрузки блокирует правку.
    # Позиция, сумма отгрузки и долг сохраняются.
    def test_recorded_shipment_blocks_reduction_even_in_processing(self):
        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        # Меняем только метку статуса, сохраняя документ отгрузки.
        # Это позволяет проверить запрет независимо от статуса.
        self.order.status = OrderStatus.PROCESSING
        self.order.save(
            update_fields=["status"],
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Order items cannot be changed after shipment.",
        ):
            reduce_order_item_quantity(
                order_item=self.order_item,
                new_quantity=5,
                changed_by=self.manager,
                reason="Customer requested fewer items.",
            )

        self.order_item.refresh_from_db()
        self.order.refresh_from_db()
        self.account.refresh_from_db()
        shipment.refresh_from_db()

        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(shipment.total_amount, Decimal("700.00"))
        self.assertEqual(shipment.items.get().quantity, 7)
        self.assertEqual(self.account.debt_balance, Decimal("700.00"))
        self.assertEqual(self.account.transactions.count(), 1)

    # Проверяем уменьшение позиции с 7 до 5:
    # освобождаются две единицы поставщика, свой резерв сохраняется.
    # Цена партии остаётся 100, сумма заказа становится 500.
    # История сохраняет изменение, сотрудника и причину.
    def test_manager_reduces_quantity_with_stock_release_and_history(self):
        self.product.base_price = Decimal("130.00")
        self.product.save(
            update_fields=["base_price"],
        )

        reason = "Customer requested fewer items."

        reduce_order_item_quantity(
            order_item=self.order_item,
            new_quantity=5,
            changed_by=self.manager,
            reason=reason,
        )

        self.order_item.refresh_from_db()
        self.order.refresh_from_db()
        self.own_supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()
        self.own_reservation.refresh_from_db()
        self.external_reservation.refresh_from_db()

        self.assertEqual(self.order_item.quantity, 5)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("500.00"))
        self.assertEqual(self.order.total_price, Decimal("500.00"))

        self.assertEqual(self.own_reservation.quantity, 4)
        self.assertEqual(self.external_reservation.quantity, 1)
        self.assertEqual(self.own_supplier_product.stock_quantity, 0)
        self.assertEqual(self.external_supplier_product.stock_quantity, 2)

        change = self.order.item_changes.get()

        self.assertEqual(change.change_type, OrderItemChangeType.REDUCED)
        self.assertEqual(change.changed_by, self.manager)
        self.assertEqual(change.reason, reason)
        self.assertEqual(change.old_quantity, 7)
        self.assertEqual(change.new_quantity, 5)
        self.assertEqual(change.unit_price, Decimal("100.00"))
        self.assertEqual(change.old_order_total, Decimal("700.00"))
        self.assertEqual(change.new_order_total, Decimal("500.00"))
        expected_before = [
            {
                "supplier_product_id": self.own_supplier_product.pk,
                "supplier_name": self.own_supplier.name,
                "is_own": True,
                "quantity": 4,
            },
            {
                "supplier_product_id": self.external_supplier_product.pk,
                "supplier_name": self.external_supplier.name,
                "is_own": False,
                "quantity": 3,
            },
        ]

        expected_after = [
            expected_before[0],
            {
                **expected_before[1],
                "quantity": 1,
            },
        ]

        self.assertEqual(
            change.reservations_before,
            expected_before,
        )
        self.assertEqual(
            change.reservations_after,
            expected_after,
        )
        self.assertEqual(
            change.order_item_id_snapshot,
            self.order_item.pk,
        )
        self.assertEqual(
            change.product_name,
            self.order_item.product_name,
        )
        self.assertEqual(
            change.currency_snapshot,
            self.order_item.currency_snapshot,
        )

    # Проверяем полный откат при сбое после записи истории:
    # восстанавливаются количество, суммы, остатки и резервы,
    # включая удалённый резерв поставщика.
    # Запись неуспешного изменения в истории не остаётся.
    def test_reduction_rolls_back_when_history_saving_fails(self):
        save_history = OrderItemChange.objects.create

        def save_history_and_fail(**data):
            save_history(**data)
            raise RuntimeError("History save interrupted.")

        with patch(
            "shop_epower.orders.services.OrderItemChange.objects.create",
            side_effect=save_history_and_fail,
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "History save interrupted.",
            ):
                reduce_order_item_quantity(
                    order_item=self.order_item,
                    new_quantity=3,
                    changed_by=self.manager,
                    reason="Customer requested fewer items.",
                )

        self.order_item.refresh_from_db()
        self.order.refresh_from_db()
        self.own_supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()
        self.own_reservation.refresh_from_db()
        self.external_reservation.refresh_from_db()

        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))
        self.assertEqual(self.order.total_price, Decimal("700.00"))

        self.assertEqual(self.own_reservation.quantity, 4)
        self.assertEqual(self.external_reservation.quantity, 3)
        self.assertEqual(self.own_supplier_product.stock_quantity, 0)
        self.assertEqual(self.external_supplier_product.stock_quantity, 0)

        self.assertFalse(self.order.item_changes.exists())

    # Проверяем автоматическое освобождение излишка предоплаты:
    # заказ 700 → 500 оставляет назначенными 500 и освобождает 200.
    # Исходное поступление и финансовая история сохраняются,
    # долг до отгрузки не возникает.
    def test_reduction_automatically_releases_excess_assigned_funds(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("700.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-edit:receipt:700",
            created_by=self.manager,
            comment="Office payment received.",
        )
        original_deposit_id = payment.deposit_transaction_id

        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("700.00"),
            operation_key="item-edit:assignment:700",
            created_by=self.manager,
        )

        reduce_order_item_quantity(
            order_item=self.order_item,
            new_quantity=5,
            changed_by=self.manager,
            reason="Customer requested fewer items.",
        )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.account.refresh_from_db()
        payment.refresh_from_db()
        assignment.refresh_from_db()

        summary = get_order_financial_summary(
            order=self.order,
        )

        self.assertEqual(
            self.account.available_balance,
            Decimal("200.00"),
        )
        self.assertEqual(
            summary["assigned_amount"],
            Decimal("500.00"),
        )
        self.assertEqual(
            summary["received_amount"],
            Decimal("700.00"),
        )

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("500.00"))
        self.assertEqual(self.order_item.quantity, 5)
        self.assertEqual(self.account.debt_balance, Decimal("0.00"))

        self.assertEqual(payment.amount, Decimal("700.00"))
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(
            payment.deposit_transaction_id,
            original_deposit_id,
        )
        self.assertEqual(
            payment.deposit_transaction.available_delta,
            Decimal("700.00"),
        )
        self.assertFalse(
            self.account.transactions.filter(
                reversal_of_id=original_deposit_id,
            ).exists()
        )

        self.assertEqual(assignment.amount, Decimal("700.00"))

    # Проверяем освобождение излишка по LIFO:
    # из назначений 400 и 300 сохраняются ранние 400,
    # а последнее заменяется назначением 100.
    # Освободившиеся 200 возвращаются на доступный баланс.
    def test_reduction_releases_latest_assignment_first(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("700.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-edit:lifo:receipt",
            created_by=self.manager,
        )

        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("400.00"),
            operation_key="item-edit:lifo:first",
            created_by=self.manager,
        )
        last_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("300.00"),
            operation_key="item-edit:lifo:last",
            created_by=self.manager,
        )

        reduce_order_item_quantity(
            order_item=self.order_item,
            new_quantity=5,
            changed_by=self.manager,
            reason="Customer requested fewer items.",
        )

        self.account.refresh_from_db()
        last_assignment.refresh_from_db()

        active_assignments = list(
            self.order.fund_assignments.filter(
                account_transaction__reversal__isnull=True,
            ).order_by("created_at", "pk")
        )

        self.assertEqual(len(active_assignments), 2)
        self.assertEqual(
            active_assignments[0].pk,
            first_assignment.pk,
        )
        self.assertEqual(
            active_assignments[0].amount,
            Decimal("400.00"),
        )
        self.assertEqual(
            active_assignments[1].amount,
            Decimal("100.00"),
        )

        # Исходное последнее назначение сохранено в истории,
        # но его списание отменено через сторно.
        self.assertEqual(
            last_assignment.amount,
            Decimal("300.00"),
        )
        self.assertTrue(
            self.account.transactions.filter(
                reversal_of_id=last_assignment.account_transaction_id,
            ).exists()
        )

        self.assertEqual(
            self.account.available_balance,
            Decimal("200.00"),
        )

    # Проверяем LIFO внутри назначения из двух поступлений:
    # ранние 400 сохраняются полностью, из поздних 300 остаются 100.
    # Источники исходного назначения сохраняются в истории.
    def test_reduction_releases_latest_deposit_part_first(self):
        first_payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("400.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-edit:sources:first-receipt",
            created_by=self.manager,
        )
        last_payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("300.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-edit:sources:last-receipt",
            created_by=self.manager,
        )

        original_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("700.00"),
            operation_key="item-edit:sources:assignment",
            created_by=self.manager,
        )

        reduce_order_item_quantity(
            order_item=self.order_item,
            new_quantity=5,
            changed_by=self.manager,
            reason="Customer requested fewer items.",
        )

        active_assignment = self.order.fund_assignments.get(
            account_transaction__reversal__isnull=True,
        )

        self.assertCountEqual(
            active_assignment.sources.values_list(
                "deposit_transaction_id",
                "amount",
            ),
            [
                (
                    first_payment.deposit_transaction_id,
                    Decimal("400.00"),
                ),
                (
                    last_payment.deposit_transaction_id,
                    Decimal("100.00"),
                ),
            ],
        )

        self.assertCountEqual(
            original_assignment.sources.values_list(
                "deposit_transaction_id",
                "amount",
            ),
            [
                (
                    first_payment.deposit_transaction_id,
                    Decimal("400.00"),
                ),
                (
                    last_payment.deposit_transaction_id,
                    Decimal("300.00"),
                ),
            ],
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("200.00"),
        )

    # Проверяем сохранение исходных источников назначения:
    # освободившееся раннее поступление другого заказа
    # не используется при уменьшении текущего заказа.
    def test_reduction_does_not_use_other_freed_deposit(self):
        other_order = create_test_order(
            user=self.user,
            customer_account=self.account,
            status=OrderStatus.PROCESSING,
            total_price=Decimal("200.00"),
        )

        record_manual_order_payment(
            order=other_order,
            amount=Decimal("200.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-edit:preserve:older-receipt",
            created_by=self.manager,
        )
        other_assignment = assign_order_funds(
            order=other_order,
            amount=Decimal("200.00"),
            operation_key="item-edit:preserve:other-assignment",
            created_by=self.manager,
        )

        current_payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("700.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-edit:preserve:current-receipt",
            created_by=self.manager,
        )
        assign_order_funds(
            order=self.order,
            amount=Decimal("700.00"),
            operation_key="item-edit:preserve:current-assignment",
            created_by=self.manager,
        )

        # Ранние 200 становятся свободными уже после того,
        # как текущему заказу назначены другие деньги.
        cancel_order_fund_assignment(
            assignment=other_assignment,
            operation_key="item-edit:preserve:cancel-other",
            created_by=self.manager,
            comment="Customer cancelled the allocation.",
        )

        reduce_order_item_quantity(
            order_item=self.order_item,
            new_quantity=5,
            changed_by=self.manager,
            reason="Customer requested fewer items.",
        )

        active_assignment = self.order.fund_assignments.get(
            account_transaction__reversal__isnull=True,
        )

        self.assertEqual(
            active_assignment.amount,
            Decimal("500.00"),
        )
        self.assertEqual(
            list(
                active_assignment.sources.values_list(
                    "deposit_transaction_id",
                    "amount",
                )
            ),
            [
                (
                    current_payment.deposit_transaction_id,
                    Decimal("500.00"),
                ),
            ],
        )

        self.account.refresh_from_db()
        self.assertEqual(
            self.account.available_balance,
            Decimal("400.00"),
        )

    # Проверяем полный откат при сбое финансовой корректировки:
    # восстанавливаются исходное назначение, баланс, заказ и резервы.
    # Сторно, новое назначение и запись изменения не сохраняются.
    def test_reduction_rolls_back_when_assignment_source_saving_fails(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("700.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-edit:rollback:receipt",
            created_by=self.manager,
        )
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("700.00"),
            operation_key="item-edit:rollback:assignment",
            created_by=self.manager,
        )

        transaction_ids_before = list(
            self.account.transactions.values_list("pk", flat=True)
        )
        save_source = OrderFundAssignmentSource.objects.create

        def save_source_and_fail(**data):
            save_source(**data)
            raise RuntimeError("Assignment source save interrupted.")

        with patch(
            "shop_epower.orders.services.OrderFundAssignmentSource.objects.create",
            side_effect=save_source_and_fail,
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Assignment source save interrupted.",
            ):
                reduce_order_item_quantity(
                    order_item=self.order_item,
                    new_quantity=5,
                    changed_by=self.manager,
                    reason="Customer requested fewer items.",
                )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.account.refresh_from_db()
        self.own_reservation.refresh_from_db()
        self.external_reservation.refresh_from_db()
        self.own_supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(
            self.order_item.total_price,
            Decimal("700.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        self.assertEqual(self.own_reservation.quantity, 4)
        self.assertEqual(self.external_reservation.quantity, 3)
        self.assertEqual(self.own_supplier_product.stock_quantity, 0)
        self.assertEqual(self.external_supplier_product.stock_quantity, 0)

        self.assertEqual(self.order.fund_assignments.count(), 1)

        active_assignment = self.order.fund_assignments.get(
            account_transaction__reversal__isnull=True,
        )
        self.assertEqual(active_assignment.pk, assignment.pk)
        self.assertEqual(
            active_assignment.amount,
            Decimal("700.00"),
        )
        self.assertEqual(
            list(
                active_assignment.sources.values_list(
                    "deposit_transaction_id",
                    "amount",
                )
            ),
            [
                (
                    payment.deposit_transaction_id,
                    Decimal("700.00"),
                ),
            ],
        )

        self.assertCountEqual(
            self.account.transactions.values_list("pk", flat=True),
            transaction_ids_before,
        )
        self.assertFalse(self.order.item_changes.exists())

    # Проверяем уменьшение заказа без излишка предоплаты:
    # назначенные 400 и свободные 300 сохраняются.
    # Дополнительного назначения и финансовых корректировок нет.
    def test_reduction_keeps_assignment_below_new_order_total(self):
        record_manual_order_payment(
            order=self.order,
            amount=Decimal("700.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-edit:no-excess:receipt",
            created_by=self.manager,
        )
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("400.00"),
            operation_key="item-edit:no-excess:assignment",
            created_by=self.manager,
        )

        transaction_ids_before = list(
            self.account.transactions.values_list("pk", flat=True)
        )

        reduce_order_item_quantity(
            order_item=self.order_item,
            new_quantity=5,
            changed_by=self.manager,
            reason="Customer requested fewer items.",
        )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        self.assertEqual(
            self.order.total_price,
            Decimal("500.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("300.00"),
        )
        self.assertEqual(
            list(
                self.order.fund_assignments.values_list(
                    "pk",
                    "amount",
                )
            ),
            [
                (assignment.pk, Decimal("400.00")),
            ],
        )
        self.assertCountEqual(
            self.account.transactions.values_list("pk", flat=True),
            transaction_ids_before,
        )

    # Проверяем освобождение излишка из нескольких назначений:
    # последнее назначение 300 отменяется полностью,
    # предыдущее 400 заменяется назначением 300.
    # На свободный баланс возвращаются 400.
    def test_reduction_releases_excess_across_multiple_assignments(self):
        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("700.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-edit:multiple:receipt",
            created_by=self.manager,
        )

        first_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("400.00"),
            operation_key="item-edit:multiple:first",
            created_by=self.manager,
        )
        last_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("300.00"),
            operation_key="item-edit:multiple:last",
            created_by=self.manager,
        )

        reduce_order_item_quantity(
            order_item=self.order_item,
            new_quantity=3,
            changed_by=self.manager,
            reason="Customer requested fewer items.",
        )

        self.order.refresh_from_db()
        self.account.refresh_from_db()

        active_assignment = self.order.fund_assignments.get(
            account_transaction__reversal__isnull=True,
        )

        self.assertEqual(
            self.order.total_price,
            Decimal("300.00"),
        )
        self.assertEqual(
            active_assignment.amount,
            Decimal("300.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("400.00"),
        )

        # Оба исходных назначения остаются в истории,
        # их списания отменены через сторно.
        for original_assignment in (
            first_assignment,
            last_assignment,
        ):
            self.assertTrue(
                self.account.transactions.filter(
                    reversal_of_id=original_assignment.account_transaction_id,
                ).exists()
            )

        self.assertEqual(
            list(
                active_assignment.sources.values_list(
                    "deposit_transaction_id",
                    "amount",
                )
            ),
            [
                (
                    payment.deposit_transaction_id,
                    Decimal("300.00"),
                ),
            ],
        )

        # Уменьшение до трёх единиц освобождает весь
        # внешний резерв и одну единицу собственного склада.
        self.own_reservation.refresh_from_db()
        self.own_supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(self.own_reservation.quantity, 3)
        self.assertFalse(
            OrderStockReservation.objects.filter(
                pk=self.external_reservation.pk,
            ).exists()
        )
        self.assertEqual(self.own_supplier_product.stock_quantity, 1)
        self.assertEqual(self.external_supplier_product.stock_quantity, 3)

    # Проверяем запрет удаления последней позиции:
    # для отказа от всего заказа используется отмена заказа.
    # Позиция, суммы, резервы и остатки сохраняются,
    # запись изменения не создаётся.
    def test_cannot_remove_last_order_item(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Cannot remove the last order item.",
        ):
            remove_order_item(
                order_item=self.order_item,
                changed_by=self.manager,
                reason="Customer requested removal.",
            )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.own_reservation.refresh_from_db()
        self.external_reservation.refresh_from_db()
        self.own_supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(
            self.order_item.total_price,
            Decimal("700.00"),
        )
        self.assertEqual(
            self.order.total_price,
            Decimal("700.00"),
        )

        self.assertEqual(self.own_reservation.quantity, 4)
        self.assertEqual(self.external_reservation.quantity, 3)
        self.assertEqual(self.own_supplier_product.stock_quantity, 0)
        self.assertEqual(self.external_supplier_product.stock_quantity, 0)

        self.assertFalse(self.order.item_changes.exists())

    # Проверяем удаление выбранной ценовой партии:
    # её товарные резервы освобождаются, итог пересчитывается,
    # другая партия сохраняет свою цену, количество и резерв.
    # История удалённой строки остаётся со снимками.
    def test_manager_removes_selected_item_with_stock_release_and_history(self):
        remaining_item, remaining_reservation = self._add_second_price_batch()

        removed_item_id = self.order_item.pk
        reason = "Customer requested removal of this price batch."

        remove_order_item(
            order_item=self.order_item,
            changed_by=self.manager,
            reason=reason,
        )

        self.assertFalse(
            OrderItem.objects.filter(pk=removed_item_id).exists()
        )
        self.assertFalse(
            OrderStockReservation.objects.filter(
                order_item_id=removed_item_id,
            ).exists()
        )

        self.order.refresh_from_db()
        remaining_item.refresh_from_db()
        remaining_reservation.refresh_from_db()
        self.own_supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(
            list(self.order.items.values_list("pk", flat=True)),
            [remaining_item.pk],
        )
        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("260.00"))

        self.assertEqual(remaining_item.quantity, 2)
        self.assertEqual(remaining_item.unit_price, Decimal("130.00"))
        self.assertEqual(remaining_item.total_price, Decimal("260.00"))
        self.assertEqual(remaining_reservation.quantity, 2)

        self.assertEqual(self.own_supplier_product.stock_quantity, 4)
        self.assertEqual(self.external_supplier_product.stock_quantity, 3)

        change = self.order.item_changes.get()

        self.assertEqual(change.change_type, OrderItemChangeType.REMOVED)
        self.assertEqual(change.order_item_id_snapshot, removed_item_id)
        self.assertEqual(change.changed_by, self.manager)
        self.assertEqual(change.reason, reason)
        self.assertEqual(change.old_quantity, 7)
        self.assertEqual(change.new_quantity, 0)
        self.assertEqual(change.unit_price, Decimal("100.00"))
        self.assertEqual(change.old_order_total, Decimal("960.00"))
        self.assertEqual(change.new_order_total, Decimal("260.00"))

        self.assertCountEqual(
            [
                (
                    part["supplier_product_id"],
                    part["quantity"],
                )
                for part in change.reservations_before
            ],
            [
                (self.own_supplier_product.pk, 4),
                (self.external_supplier_product.pk, 3),
            ],
        )
        self.assertEqual(change.reservations_after, [])

    # Проверяем освобождение излишка предоплаты при удалении:
    # заказ 960 → 260 оставляет назначенными 260,
    # а 700 возвращаются на доступный баланс.
    # Реальное поступление и исходное назначение сохраняются в истории.
    def test_removal_automatically_releases_excess_assigned_funds(self):
        self._add_second_price_batch()

        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("960.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-remove:receipt:960",
            created_by=self.manager,
        )
        original_deposit_id = payment.deposit_transaction_id

        original_assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("960.00"),
            operation_key="item-remove:assignment:960",
            created_by=self.manager,
        )

        remove_order_item(
            order_item=self.order_item,
            changed_by=self.manager,
            reason="Customer requested removal of this price batch.",
        )

        self.order.refresh_from_db()
        self.account.refresh_from_db()
        payment.refresh_from_db()
        original_assignment.refresh_from_db()

        summary = get_order_financial_summary(order=self.order)

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("260.00"))
        self.assertEqual(
            summary["assigned_amount"],
            Decimal("260.00"),
        )
        self.assertEqual(
            summary["received_amount"],
            Decimal("960.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("700.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        self.assertEqual(payment.amount, Decimal("960.00"))
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertEqual(
            payment.deposit_transaction_id,
            original_deposit_id,
        )
        self.assertEqual(
            payment.deposit_transaction.available_delta,
            Decimal("960.00"),
        )
        self.assertFalse(
            self.account.transactions.filter(
                reversal_of_id=original_deposit_id,
            ).exists()
        )

        self.assertEqual(
            original_assignment.amount,
            Decimal("960.00"),
        )

        active_assignment = self.order.fund_assignments.get(
            account_transaction__reversal__isnull=True,
        )
        self.assertEqual(
            list(
                active_assignment.sources.values_list(
                    "deposit_transaction_id",
                    "amount",
                )
            ),
            [
                (
                    original_deposit_id,
                    Decimal("260.00"),
                ),
            ],
        )

    # Проверяем полный откат удаления при финансовом сбое:
    # восстанавливаются удалённая строка, её резервы и итог заказа,
    # прежнее назначение и баланс. Новые финансовые записи
    # и история неуспешного удаления не сохраняются.
    def test_removal_rolls_back_when_assignment_source_saving_fails(self):
        remaining_item, remaining_reservation = self._add_second_price_batch()

        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("960.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-remove:rollback:receipt",
            created_by=self.manager,
        )
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("960.00"),
            operation_key="item-remove:rollback:assignment",
            created_by=self.manager,
        )

        removed_item_id = self.order_item.pk
        transaction_ids_before = list(
            self.account.transactions.values_list("pk", flat=True)
        )
        save_source = OrderFundAssignmentSource.objects.create

        def save_source_and_fail(**data):
            save_source(**data)
            raise RuntimeError("Assignment source save interrupted.")

        with patch(
            "shop_epower.orders.services.OrderFundAssignmentSource.objects.create",
            side_effect=save_source_and_fail,
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "Assignment source save interrupted.",
            ):
                remove_order_item(
                    order_item=self.order_item,
                    changed_by=self.manager,
                    reason="Customer requested removal.",
                )

        restored_item = OrderItem.objects.get(pk=removed_item_id)
        self.order.refresh_from_db()
        self.account.refresh_from_db()
        self.own_reservation.refresh_from_db()
        self.external_reservation.refresh_from_db()
        remaining_reservation.refresh_from_db()

        self.assertCountEqual(
            self.order.items.values_list("pk", flat=True),
            [removed_item_id, remaining_item.pk],
        )
        self.assertEqual(restored_item.quantity, 7)
        self.assertEqual(restored_item.total_price, Decimal("700.00"))
        self.assertEqual(self.order.total_price, Decimal("960.00"))

        self.assertEqual(self.own_reservation.quantity, 4)
        self.assertEqual(self.external_reservation.quantity, 3)
        self.assertEqual(remaining_reservation.quantity, 2)

        for source in (
            self.own_supplier_product,
            self.external_supplier_product,
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, 0)

        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(self.order.fund_assignments.count(), 1)

        active_assignment = self.order.fund_assignments.get(
            account_transaction__reversal__isnull=True,
        )
        self.assertEqual(active_assignment.pk, assignment.pk)
        self.assertEqual(active_assignment.amount, Decimal("960.00"))
        self.assertEqual(
            list(
                active_assignment.sources.values_list(
                    "deposit_transaction_id",
                    "amount",
                )
            ),
            [
                (
                    payment.deposit_transaction_id,
                    Decimal("960.00"),
                ),
            ],
        )

        self.assertCountEqual(
            self.account.transactions.values_list("pk", flat=True),
            transaction_ids_before,
        )
        self.assertFalse(self.order.item_changes.exists())

    # Проверяем запрет удаления позиции клиентом:
    # заказ принадлежит ему и содержит две строки,
    # но изменение состава доступно только сотрудникам.
    # При отказе строки, суммы и резервы сохраняются.
    def test_customer_cannot_remove_order_item(self):
        self._add_second_price_batch()

        with self.assertRaisesMessage(
            ValidationError,
            "Only managers and administrators can change order items.",
        ):
            remove_order_item(
                order_item=self.order_item,
                changed_by=self.user,
                reason="Customer requested removal.",
            )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()

        self.assertEqual(self.order.items.count(), 2)
        self.assertEqual(self.order.total_price, Decimal("960.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(
            self.order_item.total_price,
            Decimal("700.00"),
        )
        self.assertCountEqual(
            self.order_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 4),
                (self.external_supplier_product.pk, 3),
            ],
        )

        for source in (
            self.own_supplier_product,
            self.external_supplier_product,
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, 0)

        self.assertFalse(self.order.item_changes.exists())

    # Проверяем запрет удаления после записанной отгрузки:
    # даже ошибочный PROCESSING не разрешает менять состав.
    # Строки заказа, снимки отгрузки и долг сохраняются.
    def test_recorded_shipment_blocks_removal_even_in_processing(self):
        self._add_second_price_batch()

        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )
        transaction_ids_before = list(
            self.account.transactions.values_list("pk", flat=True)
        )

        # Меняем только метку статуса, сохраняя документ отгрузки.
        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        with self.assertRaisesMessage(
            ValidationError,
            "Order items cannot be changed after shipment.",
        ):
            remove_order_item(
                order_item=self.order_item,
                changed_by=self.manager,
                reason="Customer requested removal.",
            )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.account.refresh_from_db()
        shipment.refresh_from_db()

        self.assertEqual(self.order.items.count(), 2)
        self.assertEqual(self.order.total_price, Decimal("960.00"))
        self.assertEqual(self.order_item.quantity, 7)

        self.assertEqual(shipment.total_amount, Decimal("960.00"))
        self.assertCountEqual(
            shipment.items.values_list("quantity", "unit_price"),
            [
                (7, Decimal("100.00")),
                (2, Decimal("130.00")),
            ],
        )

        self.assertEqual(
            self.account.debt_balance,
            Decimal("960.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertCountEqual(
            self.account.transactions.values_list("pk", flat=True),
            transaction_ids_before,
        )
        self.assertFalse(self.order.item_changes.exists())

    # Проверяем запрет удаления при действующем Invoice:
    # сотрудник должен сначала явно аннулировать документ.
    # При отказе строки, сумма заказа и Invoice сохраняются,
    # история изменения заказа не создаётся.
    def test_cannot_remove_item_with_issued_invoice(self):
        self._add_second_price_batch()

        invoice = create_test_invoice(
            order=self.order,
            payment=None,
            amount=self.order.total_price,
            status=InvoiceStatus.ISSUED,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Cancel the issued invoice before changing order items.",
        ):
            remove_order_item(
                order_item=self.order_item,
                changed_by=self.manager,
                reason="Customer requested removal.",
            )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        invoice.refresh_from_db()

        self.assertEqual(self.order.items.count(), 2)
        self.assertEqual(self.order.total_price, Decimal("960.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(
            self.order_item.total_price,
            Decimal("700.00"),
        )

        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.amount, Decimal("960.00"))
        self.assertEqual(self.order.invoices.count(), 1)
        self.assertFalse(self.order.item_changes.exists())

    # Проверяем обязательную причину удаления:
    # None, пустая строка и пробелы отклоняются.
    # Строки и суммы сохраняются, история не создаётся.
    def test_removal_requires_nonblank_reason(self):
        self._add_second_price_batch()

        for reason in (None, "", "   "):
            with self.subTest(reason=reason):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Order item change reason is required.",
                ):
                    remove_order_item(
                        order_item=self.order_item,
                        changed_by=self.manager,
                        reason=reason,
                    )

                self.order.refresh_from_db()
                self.order_item.refresh_from_db()

                self.assertEqual(self.order.items.count(), 2)
                self.assertEqual(
                    self.order.total_price,
                    Decimal("960.00"),
                )
                self.assertEqual(self.order_item.quantity, 7)
                self.assertEqual(
                    self.order_item.total_price,
                    Decimal("700.00"),
                )
                self.assertFalse(self.order.item_changes.exists())

    # Проверяем снятие назначения после удаления позиции:
    # оставшиеся назначенные 260 возвращаются на свободный баланс.
    # Реальное поступление 960 сохраняется, заказ остаётся в работе.
    def test_retained_assignment_can_be_cancelled_after_item_removal(self):
        self._add_second_price_batch()

        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("960.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-remove:cancel-retained:receipt",
            created_by=self.manager,
        )
        assign_order_funds(
            order=self.order,
            amount=Decimal("960.00"),
            operation_key="item-remove:cancel-retained:assignment",
            created_by=self.manager,
        )

        remove_order_item(
            order_item=self.order_item,
            changed_by=self.manager,
            reason="Customer requested removal.",
        )

        retained_assignment = self.order.fund_assignments.get(
            account_transaction__reversal__isnull=True,
        )
        self.assertEqual(
            retained_assignment.amount,
            Decimal("260.00"),
        )

        cancel_order_fund_assignment(
            assignment=retained_assignment,
            operation_key="item-remove:cancel-retained:cancel",
            created_by=self.manager,
            comment="Correcting the prepayment assignment.",
        )

        self.order.refresh_from_db()
        self.account.refresh_from_db()
        payment.refresh_from_db()

        summary = get_order_financial_summary(order=self.order)

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("260.00"))
        self.assertEqual(
            summary["assigned_amount"],
            Decimal("0.00"),
        )
        self.assertEqual(
            summary["received_amount"],
            Decimal("960.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("960.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(payment.amount, Decimal("960.00"))
        self.assertEqual(payment.status, PaymentStatus.PAID)

    # Проверяем отгрузку после удаления позиции:
    # оставшаяся предоплата 260 погашает долг по отгрузке,
    # свободные 700 сохраняются.
    # Повторное завершение не создаёт новых финансовых операций.
    def test_shipment_after_item_removal_applies_retained_funds_once(self):
        remaining_item, _ = self._add_second_price_batch()

        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("960.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-remove:shipment:receipt",
            created_by=self.manager,
        )
        assign_order_funds(
            order=self.order,
            amount=Decimal("960.00"),
            operation_key="item-remove:shipment:assignment",
            created_by=self.manager,
        )

        remove_order_item(
            order_item=self.order_item,
            changed_by=self.manager,
            reason="Customer requested removal.",
        )

        retained_assignment = self.order.fund_assignments.get(
            account_transaction__reversal__isnull=True,
        )

        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )
        transaction_ids_after_completion = list(
            self.account.transactions.values_list("pk", flat=True)
        )

        repeated_shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )

        self.order.refresh_from_db()
        self.account.refresh_from_db()
        payment.refresh_from_db()
        shipment.refresh_from_db()

        self.assertEqual(repeated_shipment.pk, shipment.pk)
        self.assertEqual(self.order.shipments.count(), 1)
        self.assertEqual(self.order.status, OrderStatus.COMPLETED)
        self.assertEqual(self.order.total_price, Decimal("260.00"))
        self.assertEqual(shipment.total_amount, Decimal("260.00"))

        shipped_item = shipment.items.get()
        self.assertEqual(shipped_item.order_item_id, remaining_item.pk)
        self.assertEqual(shipped_item.quantity, 2)
        self.assertEqual(shipped_item.unit_price, Decimal("130.00"))
        self.assertEqual(shipped_item.total_price, Decimal("260.00"))

        application = retained_assignment.applications.get()
        self.assertEqual(application.shipment_id, shipment.pk)
        self.assertEqual(application.amount, Decimal("260.00"))
        self.assertEqual(
            shipment.debt_transaction.debt_delta,
            Decimal("260.00"),
        )
        self.assertEqual(
            application.account_transaction.debt_delta,
            Decimal("-260.00"),
        )
        self.assertEqual(
            application.account_transaction.available_delta,
            Decimal("0.00"),
        )

        self.assertEqual(
            self.account.available_balance,
            Decimal("700.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )
        self.assertEqual(payment.amount, Decimal("960.00"))
        self.assertEqual(payment.status, PaymentStatus.PAID)

        self.assertCountEqual(
            self.account.transactions.values_list("pk", flat=True),
            transaction_ids_after_completion,
        )

    # Проверяем добавление того же товара новой ценовой партией:
    # прежние 7 × 100 сохраняются, новые 5 получают цену 130.
    # Цена пересчитывается по поставщикам и наценке.
    # Новая строка получает отдельные резервы и запись истории.
    def test_manager_adds_same_product_as_new_price_batch(self):
        self._prepare_addition_sources()

        reason = "Customer requested five additional units."

        new_item = add_order_item(
            order=self.order,
            product=self.product,
            quantity=5,
            confirmed_unit_price=Decimal("130.00"),
            changed_by=self.manager,
            reason=reason,
        )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        new_item.refresh_from_db()

        self.assertEqual(self.order.items.count(), 2)
        self.assertNotEqual(new_item.pk, self.order_item.pk)
        self.assertEqual(new_item.order_id, self.order.pk)
        self.assertEqual(new_item.product_id, self.product.pk)

        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))

        self.assertEqual(new_item.quantity, 5)
        self.assertEqual(new_item.unit_price, Decimal("130.00"))
        self.assertEqual(new_item.total_price, Decimal("650.00"))
        self.assertEqual(
            new_item.currency_snapshot,
            self.order.currency_snapshot,
        )
        self.assertEqual(self.order.total_price, Decimal("1350.00"))
        self.assertEqual(self.order.status, OrderStatus.PROCESSING)

        self.assertCountEqual(
            self.order_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 4),
                (self.external_supplier_product.pk, 3),
            ],
        )
        self.assertCountEqual(
            new_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 2),
                (self.external_supplier_product.pk, 3),
            ],
        )

        for source in (
            self.own_supplier_product,
            self.external_supplier_product,
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, 0)

        change = self.order.item_changes.get()

        self.assertEqual(change.change_type, OrderItemChangeType.ADDED)
        self.assertEqual(change.order_item_id_snapshot, new_item.pk)
        self.assertEqual(change.changed_by, self.manager)
        self.assertEqual(change.reason, reason)
        self.assertEqual(change.unit_price, Decimal("130.00"))
        self.assertEqual(change.old_quantity, 0)
        self.assertEqual(change.new_quantity, 5)
        self.assertEqual(change.old_order_total, Decimal("700.00"))
        self.assertEqual(change.new_order_total, Decimal("1350.00"))
        self.assertEqual(change.reservations_before, [])
        self.assertCountEqual(
            [
                (
                    part["supplier_product_id"],
                    part["quantity"],
                )
                for part in change.reservations_after
            ],
            [
                (self.own_supplier_product.pk, 2),
                (self.external_supplier_product.pk, 3),
            ],
        )

    # Проверяем отказ при изменении подтверждённой цены:
    # менеджер подтвердил 130, но новая цена уже 156.
    # Заказ и прежние резервы сохраняются,
    # доступный товар не расходуется, история не создаётся.
    def test_addition_rejects_price_changed_after_confirmation(self):
        self._prepare_addition_sources()

        self.external_supplier_product.supplier_price = Decimal("120.00")
        self.external_supplier_product.save(
            update_fields=["supplier_price"],
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Product price has changed. Confirm the current price again.",
        ):
            add_order_item(
                order=self.order,
                product=self.product,
                quantity=5,
                confirmed_unit_price=Decimal("130.00"),
                changed_by=self.manager,
                reason="Customer requested additional units.",
            )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.own_supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))

        self.assertCountEqual(
            self.order_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 4),
                (self.external_supplier_product.pk, 3),
            ],
        )
        self.assertEqual(self.own_supplier_product.stock_quantity, 2)
        self.assertEqual(self.external_supplier_product.stock_quantity, 3)
        self.assertFalse(self.order.item_changes.exists())

    # Проверяем применение ценовой категории владельца заказа:
    # клиент получает скидку 10% от 130 — цену 117.
    # Категория менеджера не влияет на цену клиента.
    # Прежняя партия сохраняет цену 100.
    def test_addition_uses_order_customer_price_category(self):
        self._prepare_addition_sources()

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

        new_item = add_order_item(
            order=self.order,
            product=self.product,
            quantity=5,
            confirmed_unit_price=Decimal("117.00"),
            changed_by=self.manager,
            reason="Customer requested additional units.",
        )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.product.refresh_from_db()
        new_item.refresh_from_db()

        self.assertEqual(self.product.base_price, Decimal("130.00"))
        self.assertEqual(self.order.items.count(), 2)

        self.assertEqual(new_item.quantity, 5)
        self.assertEqual(new_item.unit_price, Decimal("117.00"))
        self.assertEqual(new_item.total_price, Decimal("585.00"))

        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))
        self.assertEqual(self.order.total_price, Decimal("1285.00"))

        change = self.order.item_changes.get()
        self.assertEqual(change.unit_price, Decimal("117.00"))
        self.assertEqual(change.new_order_total, Decimal("1285.00"))

    # Проверяем отдельную партию при совпадении цен:
    # новые пять единиц по 100 не объединяются с прежними семью.
    # Обе строки сохраняют собственные резервы.
    def test_addition_creates_separate_batch_even_at_same_price(self):
        self._prepare_addition_sources()

        markup = GlobalMarkup.objects.get()
        markup.percent = Decimal("0.00")
        markup.save(update_fields=["percent"])

        new_item = add_order_item(
            order=self.order,
            product=self.product,
            quantity=5,
            confirmed_unit_price=Decimal("100.00"),
            changed_by=self.manager,
            reason="Customer requested additional units.",
        )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        new_item.refresh_from_db()

        self.assertEqual(self.order.items.count(), 2)
        self.assertNotEqual(new_item.pk, self.order_item.pk)

        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))

        self.assertEqual(new_item.quantity, 5)
        self.assertEqual(new_item.unit_price, Decimal("100.00"))
        self.assertEqual(new_item.total_price, Decimal("500.00"))
        self.assertEqual(self.order.total_price, Decimal("1200.00"))

        self.assertCountEqual(
            self.order_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 4),
                (self.external_supplier_product.pk, 3),
            ],
        )
        self.assertCountEqual(
            new_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 2),
                (self.external_supplier_product.pk, 3),
            ],
        )

        change = self.order.item_changes.get()
        self.assertEqual(change.change_type, OrderItemChangeType.ADDED)
        self.assertEqual(change.order_item_id_snapshot, new_item.pk)
        self.assertEqual(change.old_quantity, 0)
        self.assertEqual(change.new_quantity, 5)

    # Проверяем отказ при недостатке доступного товара:
    # свободно пять единиц, запрошено шесть.
    # Заказ, прежние резервы и доступные остатки сохраняются.
    # Новая строка и история не создаются.
    def test_addition_rejects_quantity_above_available_stock(self):
        self._prepare_addition_sources()

        with self.assertRaisesMessage(
            ValidationError,
            f"Not enough stock for product: {self.product.name}",
        ):
            add_order_item(
                order=self.order,
                product=self.product,
                quantity=6,
                confirmed_unit_price=Decimal("130.00"),
                changed_by=self.manager,
                reason="Customer requested additional units.",
            )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.own_supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))

        self.assertCountEqual(
            self.order_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 4),
                (self.external_supplier_product.pk, 3),
            ],
        )
        self.assertEqual(self.own_supplier_product.stock_quantity, 2)
        self.assertEqual(self.external_supplier_product.stock_quantity, 3)
        self.assertFalse(self.order.item_changes.exists())

    # Проверяем откат добавления после сбоя сохранения истории:
    # новая строка и её резервы исчезают,
    # доступные остатки и сумма заказа восстанавливаются.
    # Прежняя партия сохраняется, история неуспешной правки отсутствует.
    def test_addition_rolls_back_when_history_saving_fails(self):
        self._prepare_addition_sources()

        save_history = OrderItemChange.objects.create

        def save_history_and_fail(**data):
            save_history(**data)
            raise RuntimeError("History save interrupted.")

        with patch(
            "shop_epower.orders.services.OrderItemChange.objects.create",
            side_effect=save_history_and_fail,
        ):
            with self.assertRaisesMessage(
                RuntimeError,
                "History save interrupted.",
            ):
                add_order_item(
                    order=self.order,
                    product=self.product,
                    quantity=5,
                    confirmed_unit_price=Decimal("130.00"),
                    changed_by=self.manager,
                    reason="Customer requested additional units.",
                )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.own_supplier_product.refresh_from_db()
        self.external_supplier_product.refresh_from_db()

        self.assertEqual(
            list(self.order.items.values_list("pk", flat=True)),
            [self.order_item.pk],
        )
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))

        self.assertCountEqual(
            self.order_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 4),
                (self.external_supplier_product.pk, 3),
            ],
        )
        self.assertEqual(self.own_supplier_product.stock_quantity, 2)
        self.assertEqual(self.external_supplier_product.stock_quantity, 3)
        self.assertFalse(self.order.item_changes.exists())

    # Проверяем сохранность денег при увеличении заказа:
    # назначенные 700 и свободные 300 остаются без изменений.
    # Добавление не создаёт долг до отгрузки
    # и не назначает свободные средства автоматически.
    def test_addition_preserves_existing_assignment_and_available_funds(self):
        self._prepare_addition_sources()

        payment = record_manual_order_payment(
            order=self.order,
            amount=Decimal("1000.00"),
            method=PaymentMethod.ON_RECEIPT,
            operation_key="item-add:funds:receipt",
            created_by=self.manager,
        )
        assignment = assign_order_funds(
            order=self.order,
            amount=Decimal("700.00"),
            operation_key="item-add:funds:assignment",
            created_by=self.manager,
        )
        transaction_ids_before = list(
            self.account.transactions.values_list("pk", flat=True)
        )

        add_order_item(
            order=self.order,
            product=self.product,
            quantity=5,
            confirmed_unit_price=Decimal("130.00"),
            changed_by=self.manager,
            reason="Customer requested additional units.",
        )

        self.order.refresh_from_db()
        self.account.refresh_from_db()
        payment.refresh_from_db()

        active_assignment = self.order.fund_assignments.get(
            account_transaction__reversal__isnull=True,
        )

        self.assertEqual(self.order.status, OrderStatus.PROCESSING)
        self.assertEqual(self.order.total_price, Decimal("1350.00"))
        self.assertEqual(active_assignment.pk, assignment.pk)
        self.assertEqual(active_assignment.amount, Decimal("700.00"))
        self.assertEqual(
            self.account.available_balance,
            Decimal("300.00"),
        )
        self.assertEqual(
            self.account.debt_balance,
            Decimal("0.00"),
        )

        self.assertEqual(self.order.payments.count(), 1)
        self.assertEqual(payment.amount, Decimal("1000.00"))
        self.assertEqual(payment.status, PaymentStatus.PAID)
        self.assertCountEqual(
            self.account.transactions.values_list("pk", flat=True),
            transaction_ids_before,
        )

    # Проверяем доступ к добавлению позиции:
    # вызов без пользователя, клиент и неактивный менеджер отклоняются.
    # Заказ, прежние резервы и доступные остатки сохраняются.
    def test_addition_requires_active_staff(self):
        self._prepare_addition_sources()

        self.manager.is_active = False
        self.manager.save(update_fields=["is_active"])

        for actor in (None, self.user, self.manager):
            with self.subTest(actor=actor):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Only managers and administrators can change order items.",
                ):
                    add_order_item(
                        order=self.order,
                        product=self.product,
                        quantity=5,
                        confirmed_unit_price=Decimal("130.00"),
                        changed_by=actor,
                        reason="Customer requested additional units.",
                    )

                self.order.refresh_from_db()
                self.order_item.refresh_from_db()

                self.assertEqual(self.order.items.count(), 1)
                self.assertEqual(
                    self.order.total_price,
                    Decimal("700.00"),
                )
                self.assertEqual(self.order_item.quantity, 7)
                self.assertFalse(self.order.item_changes.exists())

        self.assertCountEqual(
            self.order_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 4),
                (self.external_supplier_product.pk, 3),
            ],
        )

        for source, expected_quantity in (
            (self.own_supplier_product, 2),
            (self.external_supplier_product, 3),
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, expected_quantity)

    # Проверяем допустимое количество при добавлении:
    # None, bool, строка, дробное число, ноль и отрицательное отклоняются.
    # Заказ и доступные остатки сохраняются.
    def test_addition_requires_positive_integer_quantity(self):
        self._prepare_addition_sources()

        for quantity in (None, True, "5", 5.5, 0, -1):
            with self.subTest(quantity=quantity):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Quantity must be a positive integer.",
                ):
                    add_order_item(
                        order=self.order,
                        product=self.product,
                        quantity=quantity,
                        confirmed_unit_price=Decimal("130.00"),
                        changed_by=self.manager,
                        reason="Customer requested additional units.",
                    )

                self.order.refresh_from_db()
                self.order_item.refresh_from_db()

                self.assertEqual(self.order.items.count(), 1)
                self.assertEqual(
                    self.order.total_price,
                    Decimal("700.00"),
                )
                self.assertEqual(self.order_item.quantity, 7)
                self.assertEqual(
                    self.order_item.unit_price,
                    Decimal("100.00"),
                )
                self.assertEqual(
                    self.order_item.total_price,
                    Decimal("700.00"),
                )
                self.assertFalse(self.order.item_changes.exists())

        for source, expected_quantity in (
            (self.own_supplier_product, 2),
            (self.external_supplier_product, 3),
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, expected_quantity)

    # Проверяем допустимую подтверждённую цену:
    # требуется положительный конечный Decimal.
    # Неверный тип, ноль, отрицательная цена, NaN и Infinity отклоняются.
    def test_addition_requires_positive_finite_confirmed_price(self):
        self._prepare_addition_sources()

        invalid_prices = (
            None,
            "130.00",
            130.0,
            True,
            Decimal("0.00"),
            Decimal("-1.00"),
            Decimal("NaN"),
            Decimal("Infinity"),
        )

        for confirmed_price in invalid_prices:
            with self.subTest(confirmed_price=confirmed_price):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Confirmed unit price must be a positive decimal amount.",
                ):
                    add_order_item(
                        order=self.order,
                        product=self.product,
                        quantity=5,
                        confirmed_unit_price=confirmed_price,
                        changed_by=self.manager,
                        reason="Customer requested additional units.",
                    )

                self.order.refresh_from_db()
                self.order_item.refresh_from_db()

                self.assertEqual(self.order.items.count(), 1)
                self.assertEqual(
                    self.order.total_price,
                    Decimal("700.00"),
                )
                self.assertEqual(self.order_item.quantity, 7)
                self.assertFalse(self.order.item_changes.exists())

        for source, expected_quantity in (
            (self.own_supplier_product, 2),
            (self.external_supplier_product, 3),
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, expected_quantity)

    # Проверяем запрет добавления во всех статусах, кроме PROCESSING.
    # Строки, сумма заказа и доступные остатки сохраняются.
    def test_addition_requires_processing_order(self):
        self._prepare_addition_sources()

        for status in OrderStatus.values:
            if status == OrderStatus.PROCESSING:
                continue

            with self.subTest(status=status):
                self.order.status = status
                self.order.save(update_fields=["status"])

                with self.assertRaisesMessage(
                    ValidationError,
                    "Order items can be changed only for processing orders.",
                ):
                    add_order_item(
                        order=self.order,
                        product=self.product,
                        quantity=5,
                        confirmed_unit_price=Decimal("130.00"),
                        changed_by=self.manager,
                        reason="Customer requested additional units.",
                    )

                self.order.refresh_from_db()
                self.order_item.refresh_from_db()

                self.assertEqual(self.order.status, status)
                self.assertEqual(self.order.items.count(), 1)
                self.assertEqual(
                    self.order.total_price,
                    Decimal("700.00"),
                )
                self.assertEqual(self.order_item.quantity, 7)
                self.assertFalse(self.order.item_changes.exists())

        for source, expected_quantity in (
            (self.own_supplier_product, 2),
            (self.external_supplier_product, 3),
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, expected_quantity)

    # Проверяем запрет добавления после записанной отгрузки:
    # даже ошибочный PROCESSING не разрешает дополнять заказ.
    # Заказ, отгрузка, долг и доступные остатки сохраняются.
    def test_recorded_shipment_blocks_addition_even_in_processing(self):
        self._prepare_addition_sources()

        shipment = complete_order_shipment(
            order=self.order,
            created_by=self.manager,
        )
        transaction_ids_before = list(
            self.account.transactions.values_list("pk", flat=True)
        )

        # Меняем только метку статуса, сохраняя документ отгрузки.
        self.order.status = OrderStatus.PROCESSING
        self.order.save(update_fields=["status"])

        with self.assertRaisesMessage(
            ValidationError,
            "Order items cannot be changed after shipment.",
        ):
            add_order_item(
                order=self.order,
                product=self.product,
                quantity=5,
                confirmed_unit_price=Decimal("130.00"),
                changed_by=self.manager,
                reason="Customer requested additional units.",
            )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        self.account.refresh_from_db()
        shipment.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)

        self.assertEqual(shipment.total_amount, Decimal("700.00"))
        self.assertEqual(shipment.items.get().quantity, 7)
        self.assertEqual(
            self.account.debt_balance,
            Decimal("700.00"),
        )
        self.assertEqual(
            self.account.available_balance,
            Decimal("0.00"),
        )
        self.assertCountEqual(
            self.account.transactions.values_list("pk", flat=True),
            transaction_ids_before,
        )

        for source, expected_quantity in (
            (self.own_supplier_product, 2),
            (self.external_supplier_product, 3),
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, expected_quantity)

        self.assertFalse(self.order.item_changes.exists())

    # Проверяем запрет добавления при действующем Invoice:
    # перед изменением состава документ нужно явно аннулировать.
    # Заказ, Invoice и доступные остатки сохраняются.
    def test_cannot_add_item_with_issued_invoice(self):
        self._prepare_addition_sources()

        invoice = create_test_invoice(
            order=self.order,
            payment=None,
            amount=self.order.total_price,
            status=InvoiceStatus.ISSUED,
        )

        with self.assertRaisesMessage(
            ValidationError,
            "Cancel the issued invoice before changing order items.",
        ):
            add_order_item(
                order=self.order,
                product=self.product,
                quantity=5,
                confirmed_unit_price=Decimal("130.00"),
                changed_by=self.manager,
                reason="Customer requested additional units.",
            )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()
        invoice.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))

        self.assertEqual(invoice.status, InvoiceStatus.ISSUED)
        self.assertEqual(invoice.amount, Decimal("700.00"))
        self.assertEqual(self.order.invoices.count(), 1)

        for source, expected_quantity in (
            (self.own_supplier_product, 2),
            (self.external_supplier_product, 3),
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, expected_quantity)

        self.assertFalse(self.order.item_changes.exists())

    # Проверяем обязательную причину добавления:
    # None, пустая строка и пробелы отклоняются.
    # Заказ и доступные остатки сохраняются, история не создаётся.
    def test_addition_requires_nonblank_reason(self):
        self._prepare_addition_sources()

        for reason in (None, "", "   "):
            with self.subTest(reason=reason):
                with self.assertRaisesMessage(
                    ValidationError,
                    "Order item change reason is required.",
                ):
                    add_order_item(
                        order=self.order,
                        product=self.product,
                        quantity=5,
                        confirmed_unit_price=Decimal("130.00"),
                        changed_by=self.manager,
                        reason=reason,
                    )

                self.order.refresh_from_db()
                self.order_item.refresh_from_db()

                self.assertEqual(self.order.items.count(), 1)
                self.assertEqual(
                    self.order.total_price,
                    Decimal("700.00"),
                )
                self.assertEqual(self.order_item.quantity, 7)
                self.assertEqual(
                    self.order_item.unit_price,
                    Decimal("100.00"),
                )
                self.assertFalse(self.order.item_changes.exists())

        for source, expected_quantity in (
            (self.own_supplier_product, 2),
            (self.external_supplier_product, 3),
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, expected_quantity)

    # Проверяем отказ при отсутствии актуальных цен поставщиков:
    # сохранённая цена каталога 100 не заменяет новый расчёт.
    # Заказ, прежняя партия и доступные остатки сохраняются.
    def test_addition_rejects_missing_current_supplier_prices(self):
        self._prepare_addition_sources()

        for source in (
            self.own_supplier_product,
            self.external_supplier_product,
        ):
            source.supplier_price = None
            source.save(update_fields=["supplier_price"])

        with self.assertRaisesMessage(
            ValidationError,
            "No current supplier price is available for this product.",
        ):
            add_order_item(
                order=self.order,
                product=self.product,
                quantity=5,
                confirmed_unit_price=Decimal("100.00"),
                changed_by=self.manager,
                reason="Customer requested additional units.",
            )

        self.order.refresh_from_db()
        self.order_item.refresh_from_db()

        self.assertEqual(self.order.items.count(), 1)
        self.assertEqual(self.order.total_price, Decimal("700.00"))
        self.assertEqual(self.order_item.quantity, 7)
        self.assertEqual(self.order_item.unit_price, Decimal("100.00"))
        self.assertEqual(self.order_item.total_price, Decimal("700.00"))

        self.assertCountEqual(
            self.order_item.stock_reservations.values_list(
                "supplier_product_id",
                "quantity",
            ),
            [
                (self.own_supplier_product.pk, 4),
                (self.external_supplier_product.pk, 3),
            ],
        )

        for source, expected_quantity in (
            (self.own_supplier_product, 2),
            (self.external_supplier_product, 3),
        ):
            source.refresh_from_db()
            self.assertEqual(source.stock_quantity, expected_quantity)

        self.assertFalse(self.order.item_changes.exists())
