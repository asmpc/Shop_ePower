from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    Spacer,
)

from shop_epower.pdf.fonts import (
    PDF_FONT_REGULAR,
)


def safe_text(
    value,
    default="-",
) -> str:
    """
    Подготавливает значение для безопасного
    отображения внутри ReportLab Paragraph.
    """
    if value in [
        None,
        "",
    ]:
        return default

    return escape(
        str(value),
    )


def build_party_lines(
    *,
    title,
    values,
    styles,
):
    """
    Формирует содержимое блока с реквизитами
    стороны документа: продавца или покупателя.
    """
    elements = [
        Paragraph(
            safe_text(title),
            styles["PartyTitle"],
        ),
        Spacer(
            1,
            3,
        ),
    ]

    for label, value in values:
        if value in [
            None,
            "",
        ]:
            continue

        elements.append(
            Paragraph(
                (
                    f"<b>{safe_text(label)}:</b> "
                    f"{safe_text(value)}"
                ),
                styles["PartyText"],
            )
        )

    return elements


def draw_pdf_footer(
    canvas,
    document,
) -> None:
    """
    Добавляет общий footer и номер страницы
    во все PDF-документы Shop ePower.
    """
    canvas.saveState()

    page_width, _ = A4

    canvas.setFont(
        PDF_FONT_REGULAR,
        8,
    )

    canvas.setFillColor(
        colors.grey,
    )

    canvas.drawCentredString(
        page_width / 2,
        10 * mm,
        "Сформировано автоматически системой Shop ePower",
    )

    canvas.drawRightString(
        page_width - document.rightMargin,
        10 * mm,
        f"Страница {canvas.getPageNumber()}",
    )

    canvas.restoreState()