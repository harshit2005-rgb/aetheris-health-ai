"""Shared layout for clinical PDFs: lab reports and prescriptions.

Invoices (:mod:`app.services.invoice_pdf`) set the house style: Noto Sans,
the hospital's letterhead on the left, the document's title on the right, a
shaded block of who-and-when, and a footer on every page. This module gives the
clinical documents that same look, reusing the invoice's :class:`Letterhead`.

**Text is data.** :func:`para` escapes every string before ReportLab's markup
sees it, so a test name or a doctor's note can never change the document.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.services.invoice_pdf import Letterhead, letterhead_from

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import date

    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus.doctemplate import BaseDocTemplate

__all__ = [
    "INK",
    "MUTED",
    "RULE",
    "SHADE",
    "ALERT",
    "MARGIN",
    "CONTENT_WIDTH",
    "Letterhead",
    "letterhead_from",
    "PageSpec",
    "register_fonts",
    "age_and_sex",
    "para",
    "style",
    "header_block",
    "meta_block",
    "safe_filename",
    "render_pages",
]

_FONT_DIR: Final = Path(__file__).resolve().parent.parent / "assets" / "fonts"
REGULAR: Final = "NotoSans"
BOLD: Final = "NotoSans-Bold"

INK: Final = colors.HexColor("#0f1b2d")
MUTED: Final = colors.HexColor("#5b6472")
RULE: Final = colors.HexColor("#d7dce3")
SHADE: Final = colors.HexColor("#f2f4f7")
ALERT: Final = colors.HexColor("#b42318")

MARGIN: Final = 16 * mm
CONTENT_WIDTH: Final = A4[0] - 2 * MARGIN

_SEX_LABEL: Final = {"male": "Male", "female": "Female", "other": "Other"}


def register_fonts() -> None:
    """Register Noto Sans once per process (the same files invoices use)."""
    if REGULAR in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(REGULAR, str(_FONT_DIR / "NotoSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(BOLD, str(_FONT_DIR / "NotoSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(REGULAR, normal=REGULAR, bold=BOLD)


def style(size: float, *, bold: bool = False, color: Any = INK, align: int = 0) -> ParagraphStyle:
    """A paragraph style in the house font (registering the font first)."""
    register_fonts()
    return ParagraphStyle(
        name=f"c{size}{bold}{align}{color}",
        fontName=BOLD if bold else REGULAR,
        fontSize=size,
        leading=size * 1.35,
        textColor=color,
        alignment=align,
    )


def para(text: str, paragraph_style: ParagraphStyle) -> Paragraph:
    """A paragraph of plain text: escaped, so nothing in it is markup."""
    return Paragraph(escape(text).replace("\n", "<br/>"), paragraph_style)


def safe_filename(text: str, fallback: str) -> str:
    """``text`` with anything but letters, digits, ``-`` and ``_`` replaced."""
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in text)
    return cleaned or fallback


def age_and_sex(date_of_birth: date | None, sex: str | None, *, on: date) -> str:
    """``"34 y · Female"``, as a clinical document prints it.

    :param date_of_birth: The patient's date of birth, if recorded.
    :param sex: The recorded gender value (``male``, ``female``, ...).
    :param on: The day the age is counted to.
    :returns: Age in years and sex; ``"—"`` for what is unknown.
    """
    parts: list[str] = []
    if date_of_birth is not None:
        years = (
            on.year
            - date_of_birth.year
            - ((on.month, on.day) < (date_of_birth.month, date_of_birth.day))
        )
        parts.append(f"{max(years, 0)} y")
    label = _SEX_LABEL.get(sex or "")
    if label:
        parts.append(label)
    return " · ".join(parts) or "—"


def header_block(head: Letterhead, title: str, stamp: str | None = None) -> Table:
    """The letterhead on the left, the document's title (and a stamp) on the right."""
    small = style(8, color=MUTED)
    left: list[Any] = [para(head.name, style(15, bold=True))]
    left += [para(line, small) for line in head.address_lines]
    if head.contact:
        left.append(para(head.contact, small))
    right: list[Any] = [para(title, style(16, bold=True, align=TA_RIGHT))]
    if stamp:
        right.append(para(stamp, style(10, bold=True, color=ALERT, align=TA_RIGHT)))
    table = Table([[left, right]], colWidths=[CONTENT_WIDTH * 0.58, CONTENT_WIDTH * 0.42])
    table.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                ("BOTTOMPADDING", (0, 0), (-1, 0), 6),
            ]
        )
    )
    return table


def meta_block(pairs: Sequence[tuple[str, str]], columns: int = 4) -> Table:
    """A shaded grid of ``(label, value)`` pairs: patient, doctor, dates."""
    label = style(7.5, bold=True, color=MUTED)
    body = style(9)
    cells = [[para(name, label), para(value, body)] for name, value in pairs]
    rows: list[list[Any]] = []
    for start in range(0, len(cells), columns):
        chunk = cells[start : start + columns]
        chunk += [[para("", label), para("", body)]] * (columns - len(chunk))
        rows.append(chunk)
    table = Table(rows, colWidths=[CONTENT_WIDTH / columns] * columns)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), SHADE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


@dataclass(frozen=True, slots=True)
class PageSpec:
    """What every page of a document carries besides its content."""

    title: str
    author: str
    footer: str
    watermark: str | None = None


def render_pages(story: list[Any], spec: PageSpec) -> bytes:
    """Lay ``story`` out on A4 with the footer (and watermark) on every page."""
    register_fonts()
    buffer = io.BytesIO()
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=20 * mm,
        title=spec.title,
        author=spec.author,
        creator="Atheris",
    )

    def _decorate(canvas: Canvas, doc: BaseDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont(REGULAR, 7.5)
        canvas.setFillColor(MUTED)
        canvas.drawString(MARGIN, 10 * mm, spec.footer)
        canvas.drawRightString(A4[0] - MARGIN, 10 * mm, f"Page {doc.page}")
        if spec.watermark:
            canvas.setFont(BOLD, 80)
            canvas.setFillColor(colors.Color(0.71, 0.14, 0.09, alpha=0.12))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, spec.watermark)
        canvas.restoreState()

    pdf.build([*story, Spacer(1, 1)], onFirstPage=_decorate, onLaterPages=_decorate)
    return buffer.getvalue()
