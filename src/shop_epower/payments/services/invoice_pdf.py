from io import BytesIO

from reportlab.lib import colors

from reportlab.lib.pagesizes import A4

from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from shop_epower.pdf import (
    build_party_lines,
    draw_pdf_footer,
    get_pdf_styles,
    safe_text,
)

from shop_epower.payments.models import InvoiceStatus


def _build_header(
    *,
    invoice,
    styles,
):
    """
    Builds the invoice header.
    """

    header_left = [
        Paragraph(
            safe_text(
                invoice.seller_short_company_name
                or invoice.seller_company_name,
            ),
            styles["CompanyTitle"],
        ),
        Paragraph(
            "Business document",
            styles["Normal"],
        ),
    ]

    header_right = [
        Paragraph(
            "INVOICE",
            styles["InvoiceTitle"],
        ),
        Paragraph(
            (
                f"<b>Number:</b> "
                f"{safe_text(invoice.invoice_number)}"
            ),
            styles["InvoiceMeta"],
        ),
        Paragraph(
            (
                f"<b>Date:</b> "
                f"{invoice.created_at:%d.%m.%Y}"
            ),
            styles["InvoiceMeta"],
        ),
        Paragraph(
            (
                f"<b>Status:</b> "
                f"{safe_text(invoice.get_status_display())}"
            ),
            styles["InvoiceMeta"],
        ),
    ]

    header_table = Table(
        [
            [
                header_left,
                header_right,
            ]
        ],
        colWidths=[
            90 * mm,
            90 * mm,
        ],
    )

    header_table.setStyle(
        TableStyle(
            [
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
            ]
        )
    )

    return [
        header_table,
        Spacer(
            1,
            8,
        ),
    ]

def _build_parties(
    *,
    invoice,
    styles,
):
    """
    Builds seller and buyer sections.
    """

    seller_values = [
        (
            "Company",
            invoice.seller_company_name,
        ),
        (
            "Tax ID",
            invoice.seller_tax_id,
        ),
        (
            "Legal address",
            invoice.seller_legal_address,
        ),
        (
            "Actual address",
            invoice.seller_actual_address,
        ),
        (
            "Bank",
            invoice.seller_bank_name,
        ),
        (
            "Bank account",
            invoice.seller_bank_account,
        ),
        (
            "Bank code",
            invoice.seller_bank_code,
        ),
        (
            "Correspondent account",
            invoice.seller_correspondent_account,
        ),
        (
            "Phone",
            invoice.seller_phone,
        ),
        (
            "Email",
            invoice.seller_email,
        ),
    ]

    buyer_values = [
        (
            "Name",
            invoice.buyer_name,
        ),
        (
            "Email",
            invoice.buyer_email,
        ),
        (
            "Phone",
            invoice.buyer_phone,
        ),
        (
            "Address",
            invoice.buyer_address,
        ),
    ]

    if invoice.buyer_is_legal_entity:
        buyer_values.extend(
            [
                (
                    "Company",
                    invoice.buyer_company_name,
                ),
                (
                    "Tax ID",
                    invoice.buyer_tax_id,
                ),
                (
                    "Legal address",
                    invoice.buyer_legal_address,
                ),
                (
                    "Bank",
                    invoice.buyer_bank_name,
                ),
                (
                    "Bank account",
                    invoice.buyer_bank_account,
                ),
            ]
        )

    parties_table = Table(
        [
            [
                build_party_lines(
                    title="Seller",
                    values=seller_values,
                    styles=styles,
                ),
                build_party_lines(
                    title="Buyer",
                    values=buyer_values,
                    styles=styles,
                ),
            ]
        ],
        colWidths=[
            88 * mm,
            88 * mm,
        ],
        hAlign="LEFT",
    )

    parties_table.setStyle(
        TableStyle(
            [
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.grey,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    colors.lightgrey,
                ),
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.whitesmoke,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    return [
        parties_table,
        Spacer(
            1,
            16,
        ),
        Paragraph(
            "Order items",
            styles["SectionTitle"],
        ),
    ]

def _build_items_table(
    *,
    invoice,
    styles,
):
    """
    Builds the invoice order items table.
    """

    table_data = [
        [
            Paragraph(
                "#",
                styles["TableHeader"],
            ),
            Paragraph(
                "Product",
                styles["TableHeader"],
            ),
            Paragraph(
                "Quantity",
                styles["TableHeader"],
            ),
            Paragraph(
                "Unit price",
                styles["TableHeader"],
            ),
            Paragraph(
                "Total",
                styles["TableHeader"],
            ),
        ]
    ]

    for index, item in enumerate(
        invoice.order.items.all(),
        start=1,
    ):
        table_data.append(
            [
                Paragraph(
                    str(index),
                    styles["TableText"],
                ),
                Paragraph(
                    safe_text(
                        item.product_name,
                    ),
                    styles["TableText"],
                ),
                Paragraph(
                    str(item.quantity),
                    styles["TableNumber"],
                ),
                Paragraph(
                    (
                        f"{item.unit_price} "
                        f"{safe_text(item.currency_snapshot)}"
                    ),
                    styles["TableNumber"],
                ),
                Paragraph(
                    (
                        f"{item.total_price} "
                        f"{safe_text(item.currency_snapshot)}"
                    ),
                    styles["TableNumber"],
                ),
            ]
        )

    items_table = Table(
        table_data,
        colWidths=[
            10 * mm,
            75 * mm,
            25 * mm,
            35 * mm,
            35 * mm,
        ],
        repeatRows=1,
        hAlign="LEFT",
    )

    items_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, 0),
                    colors.HexColor("#E9ECEF"),
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.75,
                    colors.grey,
                ),
                (
                    "INNERGRID",
                    (0, 0),
                    (-1, -1),
                    0.25,
                    colors.lightgrey,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "TOP",
                ),
                (
                    "ALIGN",
                    (0, 1),
                    (0, -1),
                    "CENTER",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    5,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    6,
                ),
            ]
        )
    )

    return [
        items_table,
        Spacer(
            1,
            14,
        ),
    ]

def _build_total_section(
    *,
    invoice,
    styles,
):
    """
    Builds the invoice total section.
    """

    total_table = Table(
        [
            [
                Paragraph(
                    "TOTAL",
                    styles["Total"],
                ),
                Paragraph(
                    (
                        f"{invoice.amount} "
                        f"{safe_text(invoice.currency_snapshot)}"
                    ),
                    styles["Total"],
                ),
            ]
        ],
        colWidths=[
            125 * mm,
            55 * mm,
        ],
    )

    total_table.setStyle(
        TableStyle(
            [
                (
                    "LINEABOVE",
                    (0, 0),
                    (-1, 0),
                    1,
                    colors.black,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    0,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    return [
        KeepTogether(
            [
                total_table,
                Spacer(
                    1,
                    16,
                ),
            ]
        )
    ]

def _build_cancellation_section(
    *,
    invoice,
    styles,
):
    """
    Builds the invoice cancellation section.
    """

    cancellation_details = [
        Paragraph(
            "Cancellation information",
            styles["SectionTitle"],
        ),
        Paragraph(
            (
                f"<b>Comment:</b> "
                f"{safe_text(invoice.cancel_comment)}"
            ),
            styles["Normal"],
        ),
    ]

    if invoice.cancelled_at:
        cancellation_details.append(
            Paragraph(
                (
                    f"<b>Cancelled at:</b> "
                    f"{invoice.cancelled_at:%d.%m.%Y %H:%M}"
                ),
                styles["Normal"],
            )
        )

    if invoice.cancelled_by:
        cancellation_details.append(
            Paragraph(
                (
                    f"<b>Cancelled by:</b> "
                    f"{safe_text(invoice.cancelled_by)}"
                ),
                styles["Normal"],
            )
        )

    cancellation_table = Table(
        [
            [
                cancellation_details,
            ]
        ],
        colWidths=[
            180 * mm,
        ],
    )

    cancellation_table.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.mistyrose,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    0.75,
                    colors.darkred,
                ),
                (
                    "LEFTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "RIGHTPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    return [
        Spacer(
            1,
            4,
        ),
        cancellation_table,
    ]

def _build_cancelled_banner(
    *,
    styles,
):
    """
    Builds the cancelled invoice banner.
    """

    cancelled_banner = Table(
        [
            [
                Paragraph(
                    "INVOICE CANCELLED",
                    styles["CancelledTitle"],
                )
            ]
        ],
        colWidths=[
            180 * mm,
        ],
    )

    cancelled_banner.setStyle(
        TableStyle(
            [
                (
                    "BACKGROUND",
                    (0, 0),
                    (-1, -1),
                    colors.mistyrose,
                ),
                (
                    "BOX",
                    (0, 0),
                    (-1, -1),
                    1,
                    colors.darkred,
                ),
                (
                    "TOPPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
                (
                    "BOTTOMPADDING",
                    (0, 0),
                    (-1, -1),
                    8,
                ),
            ]
        )
    )

    return [
        cancelled_banner,
        Spacer(
            1,
            12,
        ),
    ]


def generate_invoice_pdf(
    *,
    invoice,
) -> bytes:
    buffer = BytesIO()

    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=invoice.invoice_number,
        author="Shop ePower",
        subject="Invoice",
        rightMargin=15 * mm,
        leftMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
    )

    styles = get_pdf_styles()

    elements = []

    elements.extend(
        _build_header(
            invoice=invoice,
            styles=styles,
        )
    )

    if invoice.status == InvoiceStatus.CANCELLED:
        elements.extend(
            _build_cancelled_banner(
                styles=styles,
            )
        )

    elements.extend(
        _build_parties(
            invoice=invoice,
            styles=styles,
        )
    )

    elements.extend(
        _build_items_table(
            invoice=invoice,
            styles=styles,
        )
    )

    elements.extend(
        _build_total_section(
            invoice=invoice,
            styles=styles,
        )
    )

    if invoice.status == InvoiceStatus.CANCELLED:
        elements.extend(
            _build_cancellation_section(
                invoice=invoice,
                styles=styles,
            )
        )

    elements.extend(
        [
            Spacer(
                1,
                18,
            ),
            Paragraph(
                "Thank you for your business.",
                styles["ThankYou"],
            ),
        ]
    )

    document.build(
        elements,
        onFirstPage=draw_pdf_footer,
        onLaterPages=draw_pdf_footer,
    )

    pdf = buffer.getvalue()
    buffer.close()

    return pdf