from reportlab.lib import colors
from reportlab.lib.enums import (
    TA_CENTER,
    TA_RIGHT,
)
from reportlab.lib.styles import (
    ParagraphStyle,
    getSampleStyleSheet,
)

from shop_epower.pdf.fonts import (
    PDF_FONT_BOLD,
    PDF_FONT_REGULAR,
    register_pdf_fonts,
)


def get_pdf_styles():
    """
    Возвращает общий набор стилей
    для PDF-документов Shop ePower.
    """
    register_pdf_fonts()

    styles = getSampleStyleSheet()

    styles["Normal"].fontName = PDF_FONT_REGULAR
    styles["Normal"].fontSize = 9
    styles["Normal"].leading = 12

    styles["Title"].fontName = PDF_FONT_BOLD
    styles["Heading1"].fontName = PDF_FONT_BOLD
    styles["Heading2"].fontName = PDF_FONT_BOLD

    styles.add(
        ParagraphStyle(
            name="CompanyTitle",
            parent=styles["Heading1"],
            fontName=PDF_FONT_BOLD,
            fontSize=18,
            leading=22,
            spaceAfter=2,
        )
    )

    styles.add(
        ParagraphStyle(
            name="InvoiceTitle",
            parent=styles["Title"],
            fontName=PDF_FONT_BOLD,
            fontSize=22,
            leading=26,
            alignment=TA_RIGHT,
            spaceAfter=2,
        )
    )

    styles.add(
        ParagraphStyle(
            name="InvoiceMeta",
            parent=styles["Normal"],
            fontName=PDF_FONT_REGULAR,
            fontSize=9,
            leading=12,
            alignment=TA_RIGHT,
        )
    )

    styles.add(
        ParagraphStyle(
            name="PartyTitle",
            parent=styles["Heading2"],
            fontName=PDF_FONT_BOLD,
            fontSize=12,
            leading=15,
            spaceAfter=2,
        )
    )

    styles.add(
        ParagraphStyle(
            name="PartyText",
            parent=styles["Normal"],
            fontName=PDF_FONT_REGULAR,
            fontSize=9,
            leading=12,
        )
    )

    styles.add(
        ParagraphStyle(
            name="SectionTitle",
            parent=styles["Heading2"],
            fontName=PDF_FONT_BOLD,
            fontSize=13,
            leading=16,
            spaceBefore=4,
            spaceAfter=8,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableHeader",
            parent=styles["Normal"],
            fontName=PDF_FONT_BOLD,
            fontSize=9,
            leading=11,
            alignment=TA_CENTER,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableText",
            parent=styles["Normal"],
            fontName=PDF_FONT_REGULAR,
            fontSize=9,
            leading=11,
        )
    )

    styles.add(
        ParagraphStyle(
            name="TableNumber",
            parent=styles["Normal"],
            fontName=PDF_FONT_REGULAR,
            fontSize=9,
            leading=11,
            alignment=TA_RIGHT,
        )
    )

    styles.add(
        ParagraphStyle(
            name="Total",
            parent=styles["Heading2"],
            fontName=PDF_FONT_BOLD,
            fontSize=14,
            leading=18,
            alignment=TA_RIGHT,
        )
    )

    styles.add(
        ParagraphStyle(
            name="CancelledTitle",
            parent=styles["Heading1"],
            fontName=PDF_FONT_BOLD,
            fontSize=18,
            leading=22,
            alignment=TA_CENTER,
            textColor=colors.darkred,
        )
    )

    styles.add(
        ParagraphStyle(
            name="ThankYou",
            parent=styles["Normal"],
            fontName=PDF_FONT_REGULAR,
            alignment=TA_CENTER,
            fontSize=9,
            textColor=colors.grey,
        )
    )

    return styles