from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


PDF_FONT_REGULAR = "ShopEPower-Regular"
PDF_FONT_BOLD = "ShopEPower-Bold"


PDF_MODULE_DIR = Path(__file__).resolve().parent

PDF_FONTS_DIR = (
    PDF_MODULE_DIR
    / "assets"
    / "fonts"
)

PDF_FONT_REGULAR_PATH = (
    PDF_FONTS_DIR
    / "DejaVuSans.ttf"
)

PDF_FONT_BOLD_PATH = (
    PDF_FONTS_DIR
    / "DejaVuSans-Bold.ttf"
)


def register_pdf_fonts() -> None:
    """
    Регистрирует Unicode-шрифты,
    используемые во всех PDF-документах проекта.
    """
    if not PDF_FONT_REGULAR_PATH.exists():
        raise FileNotFoundError(
            "PDF regular font not found: "
            f"{PDF_FONT_REGULAR_PATH}"
        )

    if not PDF_FONT_BOLD_PATH.exists():
        raise FileNotFoundError(
            "PDF bold font not found: "
            f"{PDF_FONT_BOLD_PATH}"
        )

    registered_fonts = set(
        pdfmetrics.getRegisteredFontNames()
    )

    if PDF_FONT_REGULAR not in registered_fonts:
        pdfmetrics.registerFont(
            TTFont(
                PDF_FONT_REGULAR,
                str(PDF_FONT_REGULAR_PATH),
            )
        )

    if PDF_FONT_BOLD not in registered_fonts:
        pdfmetrics.registerFont(
            TTFont(
                PDF_FONT_BOLD,
                str(PDF_FONT_BOLD_PATH),
            )
        )

    pdfmetrics.registerFontFamily(
        PDF_FONT_REGULAR,
        normal=PDF_FONT_REGULAR,
        bold=PDF_FONT_BOLD,
        italic=PDF_FONT_REGULAR,
        boldItalic=PDF_FONT_BOLD,
    )