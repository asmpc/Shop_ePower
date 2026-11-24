from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import OuterRef, Q, Subquery, Sum

from shop_epower.accounts.models import Role
from shop_epower.accounts.services.profile import (
    is_profile_complete,
)
from shop_epower.catalog.models import Product
from shop_epower.core.currency import get_base_currency
from shop_epower.finance.models import (
    AccountTransactionActorType,
    AccountTransactionType,
    CustomerAccount,
    CustomerAccountType,
)
from shop_epower.finance.services import (
    record_customer_debt,
    record_customer_funds_application,
    record_customer_funds_assignment,
    reverse_customer_transaction,
)
from shop_epower.notifications.tasks import (
    notify_managers_about_new_order,
    send_customer_order_created_email,
)
from shop_epower.orders.models import (
    Order,
    OrderFundApplication,
    OrderFundAssignment,
    OrderFundAssignmentSource,
    OrderItem,
    OrderItemChange,
    OrderItemChangeType,
    OrderShipment,
    OrderShipmentItem,
    OrderStatus,
    OrderStockReservation,
)
from shop_epower.payments.models import (
    CustomerPayoutSource,
    InvoiceStatus,
)
from shop_epower.suppliers.models import SupplierProduct
from shop_epower.suppliers.services.pricing import recalc_product_base_price


@transaction.atomic
def create_order_from_cart(
    *,
    user,
    cart,
    payment_method="",
    delivery_method="pickup",
    delivery_provider="",
    delivery_address="",
    delivery_comment="",
    order_comment="",
):
    if not user or not user.is_authenticated:
        raise ValidationError("User must be authenticated.")

    if not is_profile_complete(user):
        raise ValidationError(
            "Complete your profile before placing an order."
        )

    if cart.user_id != user.id:
        raise ValidationError("Cart does not belong to user.")

    cart_items = list(
        cart.items.select_related("product")
    )

    if not cart_items:
        raise ValidationError("Cart is empty.")


    legal_profile = getattr(user, "legal_profile", None)

    is_legal_entity = (
        legal_profile is not None
        and legal_profile.is_legal_entity
    )

    account_type = (
        CustomerAccountType.LEGAL
        if is_legal_entity
        else CustomerAccountType.PERSONAL
    )

    customer_account = CustomerAccount.objects.filter(
        user=user,
        account_type=account_type,
    ).first()

    if customer_account is None:
        raise ValidationError(
            f"{account_type.label} customer account is required to place an order."
        )

    total_price = sum(
        item.total_price for item in cart_items
    )

    order = Order.objects.create(
        user=user,
        customer_account=customer_account,
        payment_method=payment_method,
        is_legal_entity=is_legal_entity,
        customer_name=user.get_full_name() or user.username,
        customer_email=user.email,
        customer_phone=getattr(user, "phone", ""),
        company_name=legal_profile.company_name if is_legal_entity else "",
        tax_id=legal_profile.tax_id if is_legal_entity else "",
        legal_address=legal_profile.legal_address if is_legal_entity else "",
        bank_name=legal_profile.bank_name if is_legal_entity else "",
        bank_account=legal_profile.bank_account if is_legal_entity else "",
        total_price=total_price or Decimal("0.00"),
        currency_snapshot=get_base_currency(),
        delivery_method=delivery_method,
        delivery_provider=delivery_provider,
        delivery_address=delivery_address,
        delivery_comment=delivery_comment,
        order_comment=order_comment,
    )

    for cart_item in cart_items:

        reservations = reserve_stock_for_order_item(
            product=cart_item.product,
            quantity=cart_item.quantity,
        )

        order_item = OrderItem.objects.create(
            order=order,
            product=cart_item.product,
            product_name=cart_item.product.name,
            unit_price=cart_item.price_snapshot,
            quantity=cart_item.quantity,
            total_price=cart_item.total_price,
            currency_snapshot=get_base_currency(),
        )

        for reservation in reservations:
            OrderStockReservation.objects.create(
                order_item=order_item,
                supplier_product=reservation["supplier_product"],
                quantity=reservation["quantity"],
            )


    cart.is_active = False
    cart.save(update_fields=["is_active"])

    transaction.on_commit(
        lambda order_id=order.id:
        send_customer_order_created_email.delay(
            order_id,
        )
    )

    transaction.on_commit(
        lambda order_id=order.id:
        notify_managers_about_new_order.delay(
            order_id,
        )
    )

    return order

def reserve_stock_for_order_item(*, product, quantity):
    supplier_products = (
        SupplierProduct.objects
        .select_for_update()
        .filter(
            product=product,
            is_active=True,
            supplier__is_active=True,
            stock_quantity__gt=0,
        )
        .order_by(
            "-supplier__is_own",
            "lead_time_days",
            "id",
        )
    )

    total_stock = sum(
        supplier_product.stock_quantity
        for supplier_product in supplier_products
    )

    if total_stock < quantity:
        raise ValidationError(
            f"Not enough stock for product: {product.name}"
        )

    remaining_quantity = quantity

    reservations = []

    for supplier_product in supplier_products:
        if remaining_quantity <= 0:
            break

        quantity_to_reserve = min(
            supplier_product.stock_quantity,
            remaining_quantity,
        )

        supplier_product.stock_quantity -= quantity_to_reserve

        supplier_product.save(
            update_fields=["stock_quantity"]
        )

        reservations.append({
            "supplier_product": supplier_product,
            "quantity": quantity_to_reserve,
        })

        remaining_quantity -= quantity_to_reserve

    return reservations

@transaction.atomic
def cancel_new_order(*, order, user):
    if (
        getattr(user, "pk", None) is None
        or not user.is_active
    ):
        raise ValidationError(
            "Only active users can cancel orders."
        )

    order = Order.objects.select_for_update().get(
        pk=order.pk,
    )

    if order.user_id != user.id:
        raise ValidationError("Order does not belong to user.")

    if order.status != OrderStatus.NEW:
        raise ValidationError("Only new orders can be cancelled.")

    reservations = (
        OrderStockReservation.objects
        .select_related("supplier_product")
        .select_for_update()
        .filter(order_item__order=order)
    )

    for reservation in reservations:
        supplier_product = reservation.supplier_product
        supplier_product.stock_quantity += reservation.quantity
        supplier_product.save(
            update_fields=["stock_quantity"]
        )

    order.status = OrderStatus.CANCELLED
    order.save(update_fields=["status"])

    actor_type = {
        Role.MANAGER: AccountTransactionActorType.MANAGER,
        Role.ADMIN: AccountTransactionActorType.ADMIN,
    }.get(user.role, AccountTransactionActorType.CUSTOMER)

    active_assignments = order.fund_assignments.filter(
        account_transaction__reversal__isnull=True,
    ).order_by("pk")

    for assignment in active_assignments:
        _cancel_order_fund_assignment(
            assignment=assignment,
            operation_key=(
                f"order:{order.pk}:cancel:assignment:{assignment.pk}"
            ),
            actor_type=actor_type,
            created_by=user,
            comment="Funds released after customer order cancellation.",
        )

    return order

@transaction.atomic
def update_order_status_by_manager(
    *,
    order,
    user,
    new_status,
    cancellation_reason="",
    cancellation_comment="",
):
    if user.role not in ("manager", "admin"):
        raise ValidationError("Only managers and admins can update order status.")

    if new_status == OrderStatus.COMPLETED:
        shipment = complete_order_shipment(
            order=order,
            created_by=user,
        )
        return shipment.order

    order = Order.objects.select_for_update().get(
        pk=order.pk,
    )

    allowed_transitions = {
        OrderStatus.NEW: [
            OrderStatus.PROCESSING,
            OrderStatus.CANCELLED,
        ],
        OrderStatus.PROCESSING: [
             OrderStatus.CANCELLED,
        ],
    }

    allowed_next_statuses = allowed_transitions.get(
        order.status,
        [],
    )

    if new_status not in allowed_next_statuses:
        raise ValidationError("Invalid order status transition.")

    if new_status == OrderStatus.CANCELLED:
        for item in order.items.all():
            for reservation in item.stock_reservations.all():
                supplier_product = reservation.supplier_product
                supplier_product.stock_quantity += reservation.quantity
                supplier_product.save(
                    update_fields=["stock_quantity"]
                )

        order.cancellation_reason = cancellation_reason
        order.cancellation_comment = cancellation_comment

    order.status = new_status

    update_fields = ["status"]

    if new_status == OrderStatus.CANCELLED:
        update_fields.extend([
            "cancellation_reason",
            "cancellation_comment",
        ])

    order.save(
        update_fields=update_fields,
    )

    if new_status == OrderStatus.CANCELLED:
        release_comment = cancellation_comment

        if (
            not isinstance(release_comment, str)
            or not release_comment.strip()
        ):
            release_comment = "Funds released after order cancellation."

        active_assignments = order.fund_assignments.filter(
            account_transaction__reversal__isnull=True,
        ).order_by("pk")

        for assignment in active_assignments:
            cancel_order_fund_assignment(
                assignment=assignment,
                operation_key=(
                    f"order:{order.pk}:cancel:assignment:{assignment.pk}"
                ),
                created_by=user,
                comment=release_comment,
            )

    return order

def update_order_delivery_by_manager(
    *,
    order,
    user,
    delivery_method,
    delivery_provider="",
    delivery_address="",
    delivery_comment="",
    delivery_cost,
    delivery_paid_by_customer_on_receipt=False,
    manager_delivery_comment="",
):
    if user.role not in ["manager", "admin"]:
        raise ValidationError(
            "Only manager or admin can update delivery."
        )

    if order.status != OrderStatus.PROCESSING:
        raise ValidationError(
            "Delivery can be updated only for processing orders."
        )

    delivery_cost = Decimal(delivery_cost or "0.00")

    items_total = sum(
        item.total_price for item in order.items.all()
    )

    order.delivery_method = delivery_method
    order.delivery_provider = delivery_provider
    order.delivery_address = delivery_address
    order.delivery_comment = delivery_comment

    order.delivery_cost = delivery_cost
    order.delivery_paid_by_customer_on_receipt = (
        delivery_paid_by_customer_on_receipt
    )
    order.manager_delivery_comment = manager_delivery_comment

    if delivery_paid_by_customer_on_receipt:
        order.total_price = items_total
    else:
        order.total_price = items_total + delivery_cost

    order.save(
        update_fields=[
            "delivery_method",
            "delivery_provider",
            "delivery_address",
            "delivery_comment",
            "delivery_cost",
            "delivery_paid_by_customer_on_receipt",
            "manager_delivery_comment",
            "total_price",
        ]
    )

    return order

@transaction.atomic
def assign_order_funds(
    *,
    order,
    amount,
    operation_key,
    created_by,
    comment="",
):
    # Назначать средства может только активный сотрудник.
    if (
        getattr(created_by, "pk", None) is None
        or not created_by.is_active
        or created_by.role not in (Role.MANAGER, Role.ADMIN)
    ):
        raise ValidationError(
            "Only managers and administrators can assign order funds."
        )

    if not isinstance(operation_key, str) or not operation_key.strip():
        raise ValidationError("Operation key is required.")

    if len(operation_key) > 255:
        raise ValidationError("Operation key is too long.")

    locked_order = Order.objects.select_for_update().get(
        pk=order.pk,
    )

    if locked_order.status not in (
            OrderStatus.NEW,
            OrderStatus.PROCESSING,
            OrderStatus.COMPLETED,
    ):
        raise ValidationError(
            "Funds cannot be assigned to an order in this status."
        )

    shipment = None

    if locked_order.status == OrderStatus.COMPLETED:
        shipment = locked_order.shipments.filter(
            customer_account_id=locked_order.customer_account_id,
            currency_snapshot=locked_order.currency_snapshot,
        ).first()

        if shipment is None:
            raise ValidationError(
                "Completed order must have a matching shipment."
            )

    account_type = (
        CustomerAccountType.LEGAL
        if locked_order.is_legal_entity
        else CustomerAccountType.PERSONAL
    )

    account = (
        CustomerAccount.objects.select_for_update()
        .filter(
            pk=locked_order.customer_account_id,
            user_id=locked_order.user_id,
            account_type=account_type,
        )
        .first()
    )

    if account is None:
        raise ValidationError(
            "Order must reference its owner's matching customer account."
        )

    if locked_order.currency_snapshot != account.currency:
        raise ValidationError(
            "Order currency must match account currency."
        )

    actor_type = (
        AccountTransactionActorType.ADMIN
        if created_by.role == Role.ADMIN
        else AccountTransactionActorType.MANAGER
    )

    # Финансовое ядро проверяет сумму и доступный баланс.
    # Последующая ошибка откатит и эту операцию.
    account_transaction = record_customer_funds_assignment(
        account=account,
        amount=amount,
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )

    existing_assignment = OrderFundAssignment.objects.filter(
        account_transaction=account_transaction,
    ).first()

    if existing_assignment is not None:
        if existing_assignment.order_id != locked_order.pk:
            raise ValidationError(
                "Operation key is already used for another order."
            )

        return existing_assignment

    assigned_amount = (
            locked_order.fund_assignments.filter(
                account_transaction__reversal__isnull=True,
            ).aggregate(
                total=Sum("amount"),
            )["total"]
            or Decimal("0.00")
    )

    if amount > locked_order.total_price - assigned_amount:
        raise ValidationError(
            "Assignment exceeds the remaining order amount."
        )

    previous_payouts = (
        CustomerPayoutSource.objects.filter(
            deposit_transaction_id=OuterRef("pk"),
        )
        .order_by()
        .values("deposit_transaction_id")
        .annotate(total=Sum("amount"))
        .values("total")
    )

    # Источники выбираем от старых поступлений к новым.
    deposits = (
        account.transactions.filter(
            operation_type=AccountTransactionType.DEPOSIT,
            currency_snapshot=account.currency,
            reversal__isnull=True,
        )
        .annotate(
            assigned_amount=Sum(
                "order_fund_assignment_sources__amount",
                filter=Q(
                    order_fund_assignment_sources__assignment__account_transaction__reversal__isnull=True,
                ),
            ),
            paid_out_amount=Subquery(previous_payouts),
        )
        .order_by("created_at", "pk")
    )

    remaining_amount = amount
    source_parts = []

    for deposit in deposits.iterator(chunk_size=100):
        assigned_amount = deposit.assigned_amount or Decimal("0.00")
        paid_out_amount = deposit.paid_out_amount or Decimal("0.00")

        available_amount = (
            deposit.available_delta
            - assigned_amount
            - paid_out_amount
        )

        if available_amount <= Decimal("0.00"):
            continue

        part_amount = min(available_amount, remaining_amount)
        source_parts.append((deposit, part_amount))
        remaining_amount -= part_amount

        if remaining_amount == Decimal("0.00"):
            break

    if remaining_amount > Decimal("0.00"):
        raise ValidationError(
            "Not enough unassigned deposit funds."
        )

    assignment = OrderFundAssignment.objects.create(
        order=locked_order,
        account_transaction=account_transaction,
        amount=amount,
    )

    for deposit, part_amount in source_parts:
        OrderFundAssignmentSource.objects.create(
            assignment=assignment,
            deposit_transaction=deposit,
            amount=part_amount,
        )

    # После отгрузки назначенные деньги сразу погашают её долг.
    if shipment is not None:
        application_transaction = record_customer_funds_application(
            account=account,
            amount=assignment.amount,
            operation_key=(
                f"order:{locked_order.pk}:shipment:"
                f"assignment:{assignment.pk}:application"
            ),
            actor_type=actor_type,
            created_by=created_by,
            comment=comment,
        )

        OrderFundApplication.objects.create(
            assignment=assignment,
            shipment=shipment,
            account_transaction=application_transaction,
            amount=assignment.amount,
        )

    return assignment

@transaction.atomic
def _cancel_order_fund_assignment(
    *,
    assignment,
    operation_key,
    actor_type,
    created_by,
    comment,
):
    if not isinstance(comment, str) or not comment.strip():
        raise ValidationError("Cancellation comment is required.")

    if not isinstance(operation_key, str) or not operation_key.strip():
        raise ValidationError("Operation key is required.")

    if len(operation_key) > 255:
        raise ValidationError("Operation key is too long.")

    saved_assignment = OrderFundAssignment.objects.only(
        "order_id",
    ).get(pk=assignment.pk)

    locked_order = Order.objects.select_for_update().get(
        pk=saved_assignment.order_id,
    )

    if locked_order.status not in (
            OrderStatus.NEW,
            OrderStatus.PROCESSING,
            OrderStatus.CANCELLED,
            OrderStatus.COMPLETED,
    ):
        raise ValidationError(
            "Assignment cannot be cancelled in this order status."
        )

    # Соблюдаем тот же порядок блокировок: сначала заказ, затем счёт.
    account = CustomerAccount.objects.select_for_update().get(
        pk=locked_order.customer_account_id,
    )

    locked_assignment = (
        OrderFundAssignment.objects.select_for_update()
        .select_related("account_transaction")
        .get(
            pk=saved_assignment.pk,
            order=locked_order,
        )
    )
    account_transaction = locked_assignment.account_transaction

    # Отменять можно только соответствующее назначению списание.
    if (
        account_transaction.account_id != account.pk
        or account_transaction.operation_type
        != AccountTransactionType.FUNDS_ASSIGNMENT
        or account_transaction.available_delta != -locked_assignment.amount
        or account_transaction.debt_delta != Decimal("0.00")
    ):
        raise ValidationError(
            "Assignment must reference a matching funds assignment transaction."
        )

    # Сначала восстанавливаем долг, погашенный этим назначением.
    applications = (
        locked_assignment.applications
        .select_related("account_transaction")
        .order_by("pk")
    )

    for application in applications:
        reverse_customer_transaction(
            original_transaction=application.account_transaction,
            operation_key=(
                f"order-fund-application:{application.pk}:cancel"
            ),
            actor_type=actor_type,
            created_by=created_by,
            comment=comment,
        )

    return reverse_customer_transaction(
        original_transaction=account_transaction,
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )

def cancel_order_fund_assignment(
    *,
    assignment,
    operation_key,
    created_by,
    comment,
):
    if (
        getattr(created_by, "pk", None) is None
        or not created_by.is_active
        or created_by.role not in (Role.MANAGER, Role.ADMIN)
    ):
        raise ValidationError(
            "Only managers and administrators can cancel order fund assignments."
        )

    actor_type = (
        AccountTransactionActorType.ADMIN
        if created_by.role == Role.ADMIN
        else AccountTransactionActorType.MANAGER
    )

    return _cancel_order_fund_assignment(
        assignment=assignment,
        operation_key=operation_key,
        actor_type=actor_type,
        created_by=created_by,
        comment=comment,
    )

@transaction.atomic
def complete_order_shipment(
    *,
    order,
    created_by,
):
    if (
        getattr(created_by, "pk", None) is None
        or not created_by.is_active
        or created_by.role not in (Role.MANAGER, Role.ADMIN)
    ):
        raise ValidationError(
            "Only managers and administrators can complete order shipment."
        )

    locked_order = Order.objects.select_for_update().get(
        pk=order.pk,
    )

    if locked_order.status == OrderStatus.COMPLETED:
        existing_shipment = locked_order.shipments.first()

        if existing_shipment is not None:
            return existing_shipment

    if locked_order.status != OrderStatus.PROCESSING:
        raise ValidationError(
            "Only processing orders can be shipped."
        )

    order_items = list(
        locked_order.items.order_by("pk")
    )

    if not order_items:
        raise ValidationError(
            "Cannot ship an order without items."
        )

    items_total = sum(
        (order_item.total_price for order_item in order_items),
        Decimal("0.00"),
    )

    delivery_amount = (
        locked_order.delivery_cost
        or Decimal("0.00")
    )

    if locked_order.delivery_paid_by_customer_on_receipt:
        delivery_amount = Decimal("0.00")

    if locked_order.total_price != items_total + delivery_amount:
        raise ValidationError(
            "Order total does not match items and delivery."
        )

    account_type = (
        CustomerAccountType.LEGAL
        if locked_order.is_legal_entity
        else CustomerAccountType.PERSONAL
    )

    account = (
        CustomerAccount.objects.select_for_update()
        .filter(
            pk=locked_order.customer_account_id,
            user_id=locked_order.user_id,
            account_type=account_type,
        )
        .first()
    )

    if account is None:
        raise ValidationError(
            "Order must reference its owner's matching customer account."
        )

    if locked_order.currency_snapshot != account.currency:
        raise ValidationError(
            "Order currency must match account currency."
        )

    actor_type = (
        AccountTransactionActorType.ADMIN
        if created_by.role == Role.ADMIN
        else AccountTransactionActorType.MANAGER
    )

    debt_transaction = record_customer_debt(
        account=account,
        amount=locked_order.total_price,
        operation_key=f"order:{locked_order.pk}:shipment:debt",
        actor_type=actor_type,
        created_by=created_by,
    )

    shipment = OrderShipment.objects.create(
        order=locked_order,
        customer_account=account,
        debt_transaction=debt_transaction,
        total_amount=locked_order.total_price,
        currency_snapshot=locked_order.currency_snapshot,
        created_by=created_by,
    )

    for order_item in order_items:
        OrderShipmentItem.objects.create(
            shipment=shipment,
            order_item=order_item,
            product_name=order_item.product_name,
            unit_price=order_item.unit_price,
            quantity=order_item.quantity,
            total_price=order_item.total_price,
            currency_snapshot=order_item.currency_snapshot,
        )

    active_assignments = list(
        locked_order.fund_assignments.filter(
            account_transaction__reversal__isnull=True,
        ).order_by("pk")
    )

    assigned_amount = sum(
        (assignment.amount for assignment in active_assignments),
        Decimal("0.00"),
    )

    if assigned_amount > shipment.total_amount:
        raise ValidationError(
            "Assigned funds exceed the shipment amount."
        )

    for assignment in active_assignments:
        application_transaction = record_customer_funds_application(
            account=account,
            amount=assignment.amount,
            operation_key=(
                f"order:{locked_order.pk}:shipment:"
                f"assignment:{assignment.pk}:application"
            ),
            actor_type=actor_type,
            created_by=created_by,
        )

        OrderFundApplication.objects.create(
            assignment=assignment,
            shipment=shipment,
            account_transaction=application_transaction,
            amount=assignment.amount,
        )

    locked_order.status = OrderStatus.COMPLETED
    locked_order.save(
        update_fields=[
            "status",
            "updated_at",
        ],
    )

    return shipment

def _snapshot_order_item_reservations(reservations):
    return [
        {
            "supplier_product_id": reservation.supplier_product_id,
            "supplier_name": reservation.supplier_product.supplier.name,
            "is_own": reservation.supplier_product.supplier.is_own,
            "quantity": reservation.quantity,
        }
        for reservation in reservations
        if reservation.quantity > 0
    ]

def _release_excess_order_funds(*, order, change):
    active_assignments = order.fund_assignments.filter(
        account_transaction__reversal__isnull=True,
    )

    assigned_amount = active_assignments.aggregate(
        total=Sum("amount"),
    )["total"] or Decimal("0.00")

    if assigned_amount <= order.total_price:
        return

    account = CustomerAccount.objects.select_for_update().get(
        pk=order.customer_account_id,
    )

    # Сначала корректируем последние назначения — LIFO.
    assignments = list(
        active_assignments.select_for_update(of=("self",))
        .select_related("account_transaction")
        .order_by("-created_at", "-pk")
    )

    assigned_amount = sum(
        (assignment.amount for assignment in assignments),
        Decimal("0.00"),
    )
    excess = assigned_amount - order.total_price

    actor_type = (
        AccountTransactionActorType.ADMIN
        if change.changed_by.role == Role.ADMIN
        else AccountTransactionActorType.MANAGER
    )

    for assignment in assignments:
        if excess <= Decimal("0.00"):
            break

        released_amount = min(excess, assignment.amount)
        retained_amount = assignment.amount - released_amount

        source_parts = list(
            assignment.sources.filter(
                deposit_transaction__account=account,
                deposit_transaction__operation_type=(
                    AccountTransactionType.DEPOSIT
                ),
                deposit_transaction__currency_snapshot=account.currency,
                deposit_transaction__reversal__isnull=True,
            ).order_by(
                "deposit_transaction__created_at",
                "deposit_transaction_id",
            )
        )

        sources_total = sum(
            (part.amount for part in source_parts),
            Decimal("0.00"),
        )

        if sources_total != assignment.amount:
            raise ValidationError(
                "Assignment sources do not match its amount."
            )

        # Сохраняем ранние части исходных поступлений.
        # Поздние части освобождаются первыми.
        retained_parts = []
        remaining_to_keep = retained_amount

        for part in source_parts:
            if remaining_to_keep == Decimal("0.00"):
                break

            part_amount = min(part.amount, remaining_to_keep)
            retained_parts.append(
                (part.deposit_transaction_id, part_amount),
            )
            remaining_to_keep -= part_amount

        key_prefix = (
            f"order-item-change:{change.pk}:"
            f"assignment:{assignment.pk}"
        )

        cancel_order_fund_assignment(
            assignment=assignment,
            operation_key=f"{key_prefix}:cancel",
            created_by=change.changed_by,
            comment=(
                f"Funds released for order item change #{change.pk}."
            ),
        )

        if retained_amount > Decimal("0.00"):
            account_transaction = record_customer_funds_assignment(
                account=account,
                amount=retained_amount,
                operation_key=f"{key_prefix}:retain",
                actor_type=actor_type,
                created_by=change.changed_by,
                comment=(
                    f"Funds retained for order item change #{change.pk}."
                ),
            )

            replacement = OrderFundAssignment.objects.create(
                order=order,
                account_transaction=account_transaction,
                amount=retained_amount,
            )

            for deposit_id, part_amount in retained_parts:
                OrderFundAssignmentSource.objects.create(
                    assignment=replacement,
                    deposit_transaction_id=deposit_id,
                    amount=part_amount,
                )

        excess -= released_amount

@transaction.atomic
def reduce_order_item_quantity(
    *,
    order_item,
    new_quantity,
    changed_by,
    reason,
):
    if (
        getattr(changed_by, "pk", None) is None
        or not changed_by.is_active
        or changed_by.role not in (
            Role.MANAGER,
            Role.ADMIN,
        )
    ):
        raise ValidationError(
            "Only managers and administrators can change order items."
        )

    order = Order.objects.select_for_update().get(
        pk=order_item.order_id,
    )

    if order.status != OrderStatus.PROCESSING:
        raise ValidationError(
            "Order items can be changed only for processing orders."
        )

    if order.shipments.exists():
        raise ValidationError(
            "Order items cannot be changed after shipment."
        )

    if order.invoices.filter(
        status=InvoiceStatus.ISSUED,
    ).exists():
        raise ValidationError(
            "Cancel the issued invoice before changing order items."
        )

    if (
        not isinstance(reason, str)
        or not reason.strip()
    ):
        raise ValidationError(
            "Order item change reason is required."
        )

    order_item = OrderItem.objects.select_for_update().get(
        pk=order_item.pk,
        order=order,
    )

    if (
        not isinstance(new_quantity, int)
        or isinstance(new_quantity, bool)
        or new_quantity <= 0
        or new_quantity >= order_item.quantity
    ):
        raise ValidationError(
            "New quantity must be a positive integer "
            "below the current quantity."
        )

    reservations = list(
        OrderStockReservation.objects.select_for_update(of=("self",))
        .filter(order_item=order_item)
        .select_related("supplier_product__supplier")
        .order_by("pk")
    )

    reserved_quantity = sum(
        reservation.quantity
        for reservation in reservations
    )

    if reserved_quantity != order_item.quantity:
        raise ValidationError(
            "Reserved quantity does not match order item quantity."
        )

    source_ids = [
        reservation.supplier_product_id
        for reservation in reservations
    ]

    locked_sources = list(
        SupplierProduct.objects.select_for_update(of=("self",))
        .filter(pk__in=source_ids)
        .order_by("-supplier__is_own", "lead_time_days", "pk")
    )

    sources_by_id = {
        source.pk: source
        for source in locked_sources
    }

    old_quantity = order_item.quantity
    old_order_total = order.total_price

    reservations_before = _snapshot_order_item_reservations(
        reservations,
    )

    remaining_to_release = old_quantity - new_quantity

    for reservation in reversed(reservations):
        if remaining_to_release == 0:
            break

        released_quantity = min(
            reservation.quantity,
            remaining_to_release,
        )

        source = sources_by_id[reservation.supplier_product_id]
        source.stock_quantity += released_quantity
        source.save(
            update_fields=["stock_quantity", "updated_at"],
        )

        reservation.quantity -= released_quantity

        if reservation.quantity == 0:
            reservation.delete()
        else:
            reservation.save(
                update_fields=["quantity"],
            )

        remaining_to_release -= released_quantity

    order_item.quantity = new_quantity
    order_item.total_price = order_item.unit_price * new_quantity
    order_item.save(
        update_fields=["quantity", "total_price"],
    )

    items_total = order.items.aggregate(
        total=Sum("total_price"),
    )["total"] or Decimal("0.00")

    delivery_amount = order.delivery_cost or Decimal("0.00")

    if order.delivery_paid_by_customer_on_receipt:
        delivery_amount = Decimal("0.00")

    order.total_price = items_total + delivery_amount
    order.save(
        update_fields=["total_price", "updated_at"],
    )

    change = OrderItemChange.objects.create(
        order=order,
        order_item_id_snapshot=order_item.pk,
        change_type=OrderItemChangeType.REDUCED,
        product_name=order_item.product_name,
        unit_price=order_item.unit_price,
        old_quantity=old_quantity,
        new_quantity=new_quantity,
        old_order_total=old_order_total,
        new_order_total=order.total_price,
        currency_snapshot=order_item.currency_snapshot,
        reservations_before=reservations_before,
        reservations_after=_snapshot_order_item_reservations(
            reservations,
        ),
        changed_by=changed_by,
        reason=reason.strip(),
    )

    _release_excess_order_funds(
        order=order,
        change=change,
    )

    return order_item

@transaction.atomic
def remove_order_item(
    *,
    order_item,
    changed_by,
    reason,
):
    if (
        getattr(changed_by, "pk", None) is None
        or not changed_by.is_active
        or changed_by.role not in (
            Role.MANAGER,
            Role.ADMIN,
        )
    ):
        raise ValidationError(
            "Only managers and administrators can change order items."
        )

    order = Order.objects.select_for_update().get(
        pk=order_item.order_id,
    )

    if order.status != OrderStatus.PROCESSING:
        raise ValidationError(
            "Order items can be changed only for processing orders."
        )

    if order.shipments.exists():
        raise ValidationError(
            "Order items cannot be changed after shipment."
        )

    if order.invoices.filter(
        status=InvoiceStatus.ISSUED,
    ).exists():
        raise ValidationError(
            "Cancel the issued invoice before changing order items."
        )

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "Order item change reason is required."
        )

    order_item = OrderItem.objects.select_for_update().get(
        pk=order_item.pk,
        order=order,
    )

    if not order.items.exclude(pk=order_item.pk).exists():
        raise ValidationError(
            "Cannot remove the last order item."
        )

    reservations = list(
        OrderStockReservation.objects.select_for_update(of=("self",))
        .filter(order_item=order_item)
        .select_related("supplier_product__supplier")
        .order_by("pk")
    )

    reserved_quantity = sum(
        reservation.quantity
        for reservation in reservations
    )

    if reserved_quantity != order_item.quantity:
        raise ValidationError(
            "Reserved quantity does not match order item quantity."
        )

    source_ids = [
        reservation.supplier_product_id
        for reservation in reservations
    ]

    locked_sources = list(
        SupplierProduct.objects.select_for_update(of=("self",))
        .filter(pk__in=source_ids)
        .order_by("-supplier__is_own", "lead_time_days", "pk")
    )

    sources_by_id = {
        source.pk: source
        for source in locked_sources
    }

    removed_item_id = order_item.pk
    old_quantity = order_item.quantity
    old_order_total = order.total_price

    reservations_before = _snapshot_order_item_reservations(
        reservations,
    )

    # Возвращаем всё количество выбранной строки
    # в те источники, из которых оно было зарезервировано.
    for reservation in reversed(reservations):
        source = sources_by_id[reservation.supplier_product_id]
        source.stock_quantity += reservation.quantity
        source.save(
            update_fields=["stock_quantity", "updated_at"],
        )

    # Связанные резервы удаляются каскадно.
    order_item.delete()

    items_total = order.items.aggregate(
        total=Sum("total_price"),
    )["total"] or Decimal("0.00")

    delivery_amount = order.delivery_cost or Decimal("0.00")

    if order.delivery_paid_by_customer_on_receipt:
        delivery_amount = Decimal("0.00")

    order.total_price = items_total + delivery_amount
    order.save(
        update_fields=["total_price", "updated_at"],
    )

    change = OrderItemChange.objects.create(
        order=order,
        order_item_id_snapshot=removed_item_id,
        change_type=OrderItemChangeType.REMOVED,
        product_name=order_item.product_name,
        unit_price=order_item.unit_price,
        old_quantity=old_quantity,
        new_quantity=0,
        old_order_total=old_order_total,
        new_order_total=order.total_price,
        currency_snapshot=order_item.currency_snapshot,
        reservations_before=reservations_before,
        reservations_after=[],
        changed_by=changed_by,
        reason=reason.strip(),
    )

    _release_excess_order_funds(
        order=order,
        change=change,
    )

    return change

@transaction.atomic
def add_order_item(
    *,
    order,
    product,
    quantity,
    confirmed_unit_price,
    changed_by,
    reason,
):
    if (
        getattr(changed_by, "pk", None) is None
        or not changed_by.is_active
        or changed_by.role not in (
            Role.MANAGER,
            Role.ADMIN,
        )
    ):
        raise ValidationError(
            "Only managers and administrators can change order items."
        )

    order = Order.objects.select_for_update().get(
        pk=order.pk,
    )

    if order.status != OrderStatus.PROCESSING:
        raise ValidationError(
            "Order items can be changed only for processing orders."
        )

    if order.shipments.exists():
        raise ValidationError(
            "Order items cannot be changed after shipment."
        )

    if order.invoices.filter(
        status=InvoiceStatus.ISSUED,
    ).exists():
        raise ValidationError(
            "Cancel the issued invoice before changing order items."
        )

    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError(
            "Order item change reason is required."
        )

    if (
        not isinstance(quantity, int)
        or isinstance(quantity, bool)
        or quantity <= 0
    ):
        raise ValidationError(
            "Quantity must be a positive integer."
        )

    if (
        not isinstance(confirmed_unit_price, Decimal)
        or not confirmed_unit_price.is_finite()
        or confirmed_unit_price <= 0
    ):
        raise ValidationError(
            "Confirmed unit price must be a positive decimal amount."
        )

    if order.currency_snapshot != get_base_currency():
        raise ValidationError(
            "Order currency must match the current base currency."
        )

    product = Product.objects.select_for_update(
        no_key=True,
    ).get(pk=product.pk)

    if not product.is_active:
        raise ValidationError(
            "Only active products can be added to an order."
        )

    # Блокируем существующие активные источники товара
    # перед пересчётом цены и резервированием.
    price_sources = list(
        SupplierProduct.objects.select_for_update(of=("self",))
        .filter(
            product=product,
            is_active=True,
            supplier__is_active=True,
        )
        .order_by("-supplier__is_own", "lead_time_days", "pk")
    )

    if not any(
        source.supplier_price is not None
        for source in price_sources
    ):
        raise ValidationError(
            "No current supplier price is available for this product."
        )

    try:
        recalc_product_base_price(product)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc

    unit_price = product.get_price_for_user(order.user)

    if not unit_price.is_finite() or unit_price <= 0:
        raise ValidationError(
            "A positive current product price is required."
        )

    if unit_price != confirmed_unit_price:
        raise ValidationError(
            "Product price has changed. Confirm the current price again."
        )

    old_order_total = order.total_price

    reservation_parts = reserve_stock_for_order_item(
        product=product,
        quantity=quantity,
    )

    # Каждое добавление создаёт отдельную ценовую партию.
    order_item = OrderItem.objects.create(
        order=order,
        product=product,
        product_name=product.name,
        unit_price=unit_price,
        quantity=quantity,
        total_price=unit_price * quantity,
        currency_snapshot=order.currency_snapshot,
    )

    reservations = []

    for part in reservation_parts:
        reservation = OrderStockReservation.objects.create(
            order_item=order_item,
            supplier_product=part["supplier_product"],
            quantity=part["quantity"],
        )
        reservations.append(reservation)

    items_total = order.items.aggregate(
        total=Sum("total_price"),
    )["total"] or Decimal("0.00")

    delivery_amount = order.delivery_cost or Decimal("0.00")

    if order.delivery_paid_by_customer_on_receipt:
        delivery_amount = Decimal("0.00")

    order.total_price = items_total + delivery_amount
    order.save(
        update_fields=["total_price", "updated_at"],
    )

    OrderItemChange.objects.create(
        order=order,
        order_item_id_snapshot=order_item.pk,
        change_type=OrderItemChangeType.ADDED,
        product_name=order_item.product_name,
        unit_price=order_item.unit_price,
        old_quantity=0,
        new_quantity=quantity,
        old_order_total=old_order_total,
        new_order_total=order.total_price,
        currency_snapshot=order_item.currency_snapshot,
        reservations_before=[],
        reservations_after=_snapshot_order_item_reservations(
            reservations,
        ),
        changed_by=changed_by,
        reason=reason.strip(),
    )

    return order_item