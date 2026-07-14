from django.shortcuts import (
    get_object_or_404,
    redirect,
    render,
)

from django.urls import reverse

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse

from shop_epower.payments.models import (
    Invoice,
    Payment,
)
from shop_epower.payments.services import (
    generate_invoice_pdf,
    mark_payment_failed,
    mark_payment_paid,
)



def mock_checkout_view(
    request,
    transaction_id,
):
    payment = get_object_or_404(
        Payment,
        transaction_id=transaction_id,
    )

    return render(
        request,
        "payments/mock_checkout.html",
        {
            "payment": payment,
        },
    )


def mock_payment_success_view(
    request,
    transaction_id,
):
    payment = get_object_or_404(
        Payment,
        transaction_id=transaction_id,
    )

    mark_payment_paid(
        payment=payment,
        manager_comment="Mock provider payment success.",
    )

    return redirect(
        reverse(
            "orders:detail",
            args=[payment.order.id],
        )
    )


def mock_payment_fail_view(
    request,
    transaction_id,
):
    payment = get_object_or_404(
        Payment,
        transaction_id=transaction_id,
    )

    mark_payment_failed(
        payment=payment,
        manager_comment="Mock provider payment failed.",
    )

    return redirect(
        reverse(
            "orders:detail",
            args=[payment.order.id],
        )
    )

@login_required
def client_invoice_pdf_view(
    request,
    pk,
):
    invoice = get_object_or_404(
        Invoice.objects
        .select_related(
            "order",
            "payment",
        )
        .prefetch_related(
            "order__items",
        ),
        pk=pk,
        order__user=request.user,
    )

    pdf = generate_invoice_pdf(
        invoice=invoice,
    )

    response = HttpResponse(
        pdf,
        content_type="application/pdf",
    )

    response["Content-Disposition"] = (
        f'attachment; filename="{invoice.invoice_number}.pdf"'
    )

    return response