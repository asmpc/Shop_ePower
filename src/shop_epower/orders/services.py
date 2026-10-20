from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, Sum

from shop_epower.accounts.models import Role
from shop_epower.accounts.services.profile import (
    is_profile_complete,
)
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
    OrderShipment,
    OrderShipmentItem,
    OrderStatus,
    OrderStockReservation,
)
from shop_epower.suppliers.models import SupplierProduct


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
    ):
        raise ValidationError(
            "Funds can currently be assigned only before shipment."
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
        )
        .order_by("created_at", "pk")
    )

    remaining_amount = amount
    source_parts = []

    for deposit in deposits.iterator(chunk_size=100):
        used_amount = deposit.assigned_amount or Decimal("0.00")
        available_amount = deposit.available_delta - used_amount

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
    ):
        raise ValidationError(
            "Assignments can currently be cancelled only before shipment."
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