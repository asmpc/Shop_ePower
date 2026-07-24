from shop_epower.orders.models import (
    DeliveryMethod,
    OrderStatus,
)

from django.shortcuts import get_object_or_404

from shop_epower.payments.models import (
    Invoice,
)


class InvoiceWorkflowState:
    TAKE_TO_PROCESSING = "take_to_processing"
    DELIVERY_PROVIDER_REQUIRED = "delivery_provider_required"
    DELIVERY_ADDRESS_REQUIRED = "delivery_address_required"
    DELIVERY_COST_REQUIRED = "delivery_cost_required"
    READY = "ready"


def get_invoice_workflow_state(
    *,
    order,
) -> str:
    """
    Возвращает текущий этап подготовки заказа
    к генерации Invoice менеджером.
    """
    if order.status != OrderStatus.PROCESSING:
        return InvoiceWorkflowState.TAKE_TO_PROCESSING

    if order.delivery_method != DeliveryMethod.SHIPPING:
        return InvoiceWorkflowState.READY

    if not order.delivery_provider:
        return InvoiceWorkflowState.DELIVERY_PROVIDER_REQUIRED

    if not order.delivery_address:
        return InvoiceWorkflowState.DELIVERY_ADDRESS_REQUIRED

    if order.delivery_cost is None:
        return InvoiceWorkflowState.DELIVERY_COST_REQUIRED

    return InvoiceWorkflowState.READY


def get_invoice_for_user(
    *,
    payment_id,
    user,
):
    return get_object_or_404(
        Invoice.objects
        .select_related(
            "payment",
            "order",
        )
        .prefetch_related(
            "order__items",
        ),
        payment_id=payment_id,
        payment__order__user=user,
    )