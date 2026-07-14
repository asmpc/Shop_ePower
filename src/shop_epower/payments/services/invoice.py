from django.utils import timezone

from django.core.exceptions import ValidationError

from shop_epower.payments.selectors import (
    get_company_settings,
)

from shop_epower.payments.models import (
    CompanySettings,
    PaymentMethod,
    Invoice,
    InvoiceStatus,
)


def generate_invoice_number():
    current_year = timezone.now().year

    invoices_count = Invoice.objects.filter(
        created_at__year=current_year,
    ).count()

    next_number = invoices_count + 1

    return (
        f"INV-{current_year}-"
        f"{next_number:06d}"
    )

def create_invoice_for_payment(
    *,
    payment,
):
    if payment.method != PaymentMethod.INVOICE:
        raise ValidationError(
            "Invoice can be created only for invoice payment method."
        )

    if hasattr(
        payment,
        "invoice",
    ):
        raise ValidationError(
            "Invoice already exists for this payment."
        )

    company_settings = get_company_settings()

    if company_settings is None:
        raise ValidationError(
            "Company settings are required to create invoice."
        )

    order = payment.order

    if not order.customer_name:
        raise ValidationError(
            "Customer name is required to create invoice."
        )

    if not order.customer_email:
        raise ValidationError(
            "Customer email is required to create invoice."
        )

    if not order.customer_phone:
        raise ValidationError(
            "Customer phone is required to create invoice."
        )

    if order.is_legal_entity:
        if not order.company_name:
            raise ValidationError(
                "Company name is required to create invoice."
            )

        if not order.tax_id:
            raise ValidationError(
                "Tax ID is required to create invoice."
            )

        if not order.legal_address:
            raise ValidationError(
                "Legal address is required to create invoice."
            )

    return Invoice.objects.create(
        order=order,
        payment=payment,
        invoice_number=generate_invoice_number(),

        seller_company_name=company_settings.company_name,
        seller_short_company_name=company_settings.short_company_name,
        seller_tax_id=company_settings.tax_id,
        seller_tax_registration_reason_code=(
            company_settings.tax_registration_reason_code
        ),
        seller_state_registration_number=(
            company_settings.state_registration_number
        ),
        seller_legal_address=company_settings.legal_address,
        seller_actual_address=company_settings.actual_address,
        seller_bank_name=company_settings.bank_name,
        seller_bank_account=company_settings.bank_account,
        seller_bank_code=company_settings.bank_code,
        seller_correspondent_account=(
            company_settings.correspondent_account
        ),
        seller_phone=company_settings.phone,
        seller_email=company_settings.email,

        buyer_name=order.customer_name,
        buyer_email=order.customer_email,
        buyer_phone=order.customer_phone,
        buyer_address=order.delivery_address or "",

        buyer_is_legal_entity=order.is_legal_entity,
        buyer_company_name=order.company_name or "",
        buyer_tax_id=order.tax_id or "",
        buyer_legal_address=order.legal_address or "",
        buyer_bank_name=order.bank_name or "",
        buyer_bank_account=order.bank_account or "",

        amount=payment.amount,
        currency_snapshot=payment.currency_snapshot,
    )

def cancel_invoice(
    *,
    invoice,
    cancelled_by,
    comment="",
):
    if invoice.status == InvoiceStatus.CANCELLED:
        raise ValidationError(
            "Invoice is already cancelled."
        )

    if not comment.strip():
        raise ValidationError(
            "Cancellation comment is required."
        )
    invoice.status = InvoiceStatus.CANCELLED
    invoice.cancel_comment = comment
    invoice.cancelled_at = timezone.now()
    invoice.cancelled_by = cancelled_by

    invoice.save(
        update_fields=[
            "status",
            "cancel_comment",
            "cancelled_at",
            "cancelled_by",
            "updated_at",
        ]
    )

    return invoice