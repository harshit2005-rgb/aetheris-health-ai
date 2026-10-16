"""Invoice PDFs (``docs/modules/06-billing.md`` §9, §12, AC-5).

Two steps, kept apart so each can be tested on its own:

1. :func:`build_invoice_document` turns an invoice, its payments and refunds,
   and the hospital's letterhead into an :class:`InvoiceDocument`: every
   string the PDF will show, already formatted. The amounts are the invoice's
   own, as the API returns them, so the PDF matches the on-screen invoice line
   for line (AC-5). Nothing is recomputed here.
2. :func:`render_invoice_pdf` lays that document out on A4 with ReportLab.

**Text is data.** Every value from the database — a line description, a
patient's name, a payment reference — is escaped before ReportLab's Paragraph
markup sees it, so ``<b>`` or ``<img src=…>`` in a description prints as those
characters and cannot change the document.

**Fonts.** Noto Sans (SIL Open Font License, ``app/assets/fonts``), embedded,
because the built-in PDF fonts have no rupee sign.

**Tax.** One tax line, the sum of the line taxes (founder's decision,
2026-10-16). The CGST/SGST/IGST split is v2.1 (§19, §20). The hospital's GSTIN
is printed when ``hospitals.settings["billing"]["gstin"]`` holds one.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.constants import InvoiceStatus

if TYPE_CHECKING:
    from collections.abc import Sequence
    from datetime import datetime

    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus.doctemplate import BaseDocTemplate

    from app.models.billing import PaymentMethod
    from app.schemas.billing import InvoiceResponse, PaymentResponse, RefundResponse

__all__ = [
    "Letterhead",
    "InvoiceDocument",
    "build_invoice_document",
    "format_money",
    "render_invoice_pdf",
]

_FONT_DIR: Final = Path(__file__).resolve().parent.parent / "assets" / "fonts"
_REGULAR: Final = "NotoSans"
_BOLD: Final = "NotoSans-Bold"

_INK: Final = colors.HexColor("#0f1b2d")
_MUTED: Final = colors.HexColor("#5b6472")
_RULE: Final = colors.HexColor("#d7dce3")
_SHADE: Final = colors.HexColor("#f2f4f7")

_CURRENCY_SIGN: Final = {"INR": "₹"}

_METHOD_LABEL: Final = {
    "cash": "Cash",
    "card": "Card",
    "upi": "UPI",
    "bank_transfer": "Bank transfer",
    "insurance": "Insurance",
}

#: The word stamped on an invoice that is not simply awaiting payment.
_STAMP: Final = {
    InvoiceStatus.PAID: "PAID",
    InvoiceStatus.PARTIALLY_PAID: "PARTIALLY PAID",
    InvoiceStatus.VOID: "VOID",
    InvoiceStatus.REFUNDED: "REFUNDED",
}


@dataclass(frozen=True, slots=True)
class Letterhead:
    """The hospital as the top of its invoices shows it."""

    name: str
    address_lines: tuple[str, ...]
    contact: str | None
    gstin: str | None
    timezone: str


@dataclass(frozen=True, slots=True)
class InvoiceDocument:
    """Every string an invoice PDF shows, formatted. Built by :func:`build_invoice_document`."""

    letterhead: Letterhead
    invoice_number: str
    status_stamp: str | None
    issued_on: str
    patient_name: str
    patient_mrn: str | None
    #: ``(position, description, quantity, unit price, tax %, line total)``.
    lines: tuple[tuple[str, str, str, str, str, str], ...]
    #: ``(label, amount)``, in the order the totals block shows them.
    totals: tuple[tuple[str, str], ...]
    discount_reason: str | None
    #: ``(date, method, reference, amount)``.
    payments: tuple[tuple[str, str, str, str], ...]
    #: ``(date, method, reason, amount)``.
    refunds: tuple[tuple[str, str, str, str], ...]
    notes: str | None
    #: Why a void invoice was voided.
    void_reason: str | None
    generated_at: str


# ── Formatting ───────────────────────────────────────────────────────────────


def _group_indian(whole: str) -> str:
    """Group digits the Indian way: 12,34,567."""
    if len(whole) <= 3:
        return whole
    head, tail = whole[:-3], whole[-3:]
    pairs: list[str] = []
    while len(head) > 2:
        pairs.insert(0, head[-2:])
        head = head[:-2]
    if head:
        pairs.insert(0, head)
    return ",".join([*pairs, tail])


def format_money(amount: Decimal, currency: str) -> str:
    """An amount as an invoice prints it: ``₹1,23,456.00``, or ``USD 1,234.00``.

    Rupees are grouped in lakhs and crores; other currencies in thousands, with
    the ISO code in front.

    :param amount: The amount, already exact to the minor unit.
    :param currency: The ISO 4217 code.
    :returns: The amount with its currency.
    """
    quantised = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    sign = "-" if quantised < 0 else ""
    whole, _, fraction = f"{abs(quantised):.2f}".partition(".")
    if currency == "INR":
        return f"{sign}{_CURRENCY_SIGN['INR']}{_group_indian(whole)}.{fraction}"
    return f"{sign}{currency} {int(whole):,}.{fraction}"


def _quantity(value: Decimal) -> str:
    """A quantity without trailing zeros: 1, 2.5, 10."""
    return f"{value.normalize():f}"


def _percent(value: Decimal) -> str:
    """A tax rate: 0%, 5%, 12.5%."""
    return f"{_quantity(value)}%"


def _day(moment: datetime, zone: ZoneInfo) -> str:
    """A date on the hospital's clock: 16 Oct 2026."""
    return moment.astimezone(zone).strftime("%d %b %Y")


def _method(method: PaymentMethod | str) -> str:
    """A payment method as a person writes it."""
    value = str(method.value if hasattr(method, "value") else method)
    return _METHOD_LABEL.get(value, value.replace("_", " ").capitalize())


# ── Building the document ────────────────────────────────────────────────────


def letterhead_from(hospital: Any) -> Letterhead:
    """Read a hospital row into a :class:`Letterhead`.

    :param hospital: The ``Hospital`` ORM row.
    :returns: The letterhead.
    """
    address: dict[str, Any] = hospital.address or {}

    def part(*keys: str) -> str:
        # The canonical keys are line1/line2/postal_code (the same as patients);
        # street/zip are read too, for an address saved before they settled.
        return next(
            (str(address[k]).strip() for k in keys if str(address.get(k) or "").strip()), ""
        )

    street = ", ".join(p for p in (part("line1", "street"), part("line2")) if p)
    city_line = ", ".join(
        p
        for p in (
            part("city"),
            " ".join(q for q in (part("state"), part("postal_code", "zip")) if q),
        )
        if p
    )
    country = str(address.get("country") or "").strip()
    contact = " · ".join(p for p in (hospital.phone, hospital.email) if p) or None
    settings: dict[str, Any] = hospital.settings or {}
    billing = settings.get("billing") if isinstance(settings.get("billing"), dict) else {}
    gstin = billing.get("gstin") if isinstance(billing, dict) else None
    return Letterhead(
        name=hospital.name,
        address_lines=tuple(line for line in (street, city_line, country) if line),
        contact=contact,
        gstin=(str(gstin).strip() or None) if gstin else None,
        timezone=hospital.timezone,
    )


def build_invoice_document(
    invoice: InvoiceResponse,
    *,
    letterhead: Letterhead,
    patient_mrn: str | None,
    payments: Sequence[PaymentResponse],
    refunds: Sequence[RefundResponse],
    generated_at: datetime,
) -> InvoiceDocument:
    """Everything the PDF shows, from the invoice exactly as the API returns it.

    :param invoice: The invoice DTO. It must not be a draft.
    :param letterhead: The hospital's letterhead.
    :param patient_mrn: The patient's MRN, if known.
    :param payments: Payments recorded against the invoice, oldest first.
    :param refunds: Refunds given against the invoice, oldest first.
    :param generated_at: When the PDF is made (UTC).
    :returns: The document.
    :raises ValueError: If the invoice is a draft (no number, no issue date).
    """
    if invoice.invoice_number is None or invoice.issued_at is None:
        msg = "A draft invoice has no PDF."
        raise ValueError(msg)
    zone = ZoneInfo(letterhead.timezone)
    money = invoice.currency

    lines = tuple(
        (
            str(index),
            item.description,
            _quantity(item.quantity),
            format_money(item.unit_price, money),
            _percent(item.tax_rate),
            format_money(item.line_total, money),
        )
        for index, item in enumerate(sorted(invoice.items, key=lambda i: i.position), start=1)
    )
    totals: list[tuple[str, str]] = [
        ("Subtotal", format_money(invoice.subtotal, money)),
        ("Tax", format_money(invoice.tax_amount, money)),
    ]
    if invoice.discount_amount > 0:
        totals.append(("Discount", format_money(-invoice.discount_amount, money)))
    totals.append(("Total", format_money(invoice.total, money)))
    totals.append(("Paid", format_money(invoice.amount_paid, money)))
    if invoice.amount_refunded > 0:
        totals.append(("Refunded", format_money(invoice.amount_refunded, money)))
    if invoice.status is not InvoiceStatus.VOID:
        totals.append(("Outstanding", format_money(invoice.balance_due, money)))

    return InvoiceDocument(
        letterhead=letterhead,
        invoice_number=invoice.invoice_number,
        status_stamp=_STAMP.get(invoice.status),
        issued_on=_day(invoice.issued_at, zone),
        patient_name=invoice.patient_name,
        patient_mrn=patient_mrn,
        lines=lines,
        totals=tuple(totals),
        discount_reason=invoice.discount_reason if invoice.discount_amount > 0 else None,
        payments=tuple(
            (
                _day(p.received_at, zone),
                _method(p.method),
                p.reference or "—",
                format_money(p.amount, money),
            )
            for p in payments
        ),
        refunds=tuple(
            (_day(r.refunded_at, zone), _method(r.method), r.reason, format_money(r.amount, money))
            for r in refunds
        ),
        notes=invoice.notes,
        void_reason=invoice.void_reason if invoice.status is InvoiceStatus.VOID else None,
        generated_at=generated_at.astimezone(zone).strftime("%d %b %Y, %H:%M")
        + f" ({letterhead.timezone})",
    )


# ── Rendering ────────────────────────────────────────────────────────────────


def _register_fonts() -> None:
    """Register Noto Sans once per process."""
    if _REGULAR in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(_REGULAR, str(_FONT_DIR / "NotoSans-Regular.ttf")))
    pdfmetrics.registerFont(TTFont(_BOLD, str(_FONT_DIR / "NotoSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(_REGULAR, normal=_REGULAR, bold=_BOLD)


def _style(size: float, *, bold: bool = False, color: Any = _INK, align: int = 0) -> ParagraphStyle:
    return ParagraphStyle(
        name=f"s{size}{bold}{align}",
        fontName=_BOLD if bold else _REGULAR,
        fontSize=size,
        leading=size * 1.35,
        textColor=color,
        alignment=align,
    )


def _p(text: str, style: ParagraphStyle) -> Paragraph:
    """A paragraph of plain text: escaped, so nothing in it is markup."""
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def render_invoice_pdf(document: InvoiceDocument) -> bytes:
    """Lay the document out on A4 and return the PDF.

    :param document: What to print.
    :returns: The PDF file's bytes.
    """
    _register_fonts()
    buffer = io.BytesIO()
    margin = 16 * mm
    pdf = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=20 * mm,
        title=f"Invoice {document.invoice_number}",
        author=document.letterhead.name,
        creator="Atheris",
    )
    width = A4[0] - 2 * margin
    body = _style(9)
    small = _style(8, color=_MUTED)
    label = _style(8, bold=True, color=_MUTED)
    right = _style(9, align=TA_RIGHT)
    right_bold = _style(10, bold=True, align=TA_RIGHT)

    story: list[Any] = []

    # Letterhead and title.
    head = document.letterhead
    left_block = [_p(head.name, _style(15, bold=True))]
    left_block += [_p(line, small) for line in head.address_lines]
    if head.contact:
        left_block.append(_p(head.contact, small))
    if head.gstin:
        left_block.append(_p(f"GSTIN: {head.gstin}", small))
    right_block = [_p("INVOICE", _style(18, bold=True, align=TA_RIGHT))]
    if document.status_stamp:
        stamp_color = (
            colors.HexColor("#b42318")
            if document.status_stamp == "VOID"
            else colors.HexColor("#067647")
        )
        right_block.append(
            _p(document.status_stamp, _style(11, bold=True, color=stamp_color, align=TA_RIGHT))
        )
    top = Table([[left_block, right_block]], colWidths=[width * 0.62, width * 0.38])
    top.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    story += [top, Spacer(1, 6 * mm)]

    # Who and when.
    meta = [
        [
            _p("Invoice number", label),
            _p("Date issued", label),
            _p("Billed to", label),
            _p("MRN", label),
        ],
        [
            _p(document.invoice_number, body),
            _p(document.issued_on, body),
            _p(document.patient_name, body),
            _p(document.patient_mrn or "—", body),
        ],
    ]
    meta_table = Table(meta, colWidths=[width * 0.25] * 4)
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), _SHADE),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story += [meta_table, Spacer(1, 6 * mm)]

    # The lines.
    header = [_p(h, label) for h in ("#", "Description")] + [
        Paragraph(h, _style(8, bold=True, color=_MUTED, align=TA_RIGHT))
        for h in ("Qty", "Unit price", "Tax", "Amount")
    ]
    rows = [header] + [
        [
            _p(n, body),
            _p(desc, body),
            _p(qty, right),
            _p(price, right),
            _p(tax, right),
            _p(total, right),
        ]
        for n, desc, qty, price, tax, total in document.lines
    ]
    lines_table = Table(
        rows,
        colWidths=[width * f for f in (0.06, 0.44, 0.09, 0.15, 0.09, 0.17)],
        repeatRows=1,
    )
    lines_table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, _INK),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, _RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story += [lines_table, Spacer(1, 4 * mm)]

    # The totals, right-aligned.
    total_rows = []
    for name, amount in document.totals:
        strong = name in {"Total", "Outstanding"}
        total_rows.append(
            [
                _p(name, _style(10 if strong else 9, bold=strong, align=TA_RIGHT)),
                _p(amount, right_bold if strong else right),
            ]
        )
    totals_table = Table(total_rows, colWidths=[width * 0.25, width * 0.2], hAlign="RIGHT")
    names = [name for name, _ in document.totals]
    style: list[tuple[Any, ...]] = [
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if "Total" in names:
        style.append(
            ("LINEABOVE", (0, names.index("Total")), (-1, names.index("Total")), 0.8, _INK)
        )
    totals_table.setStyle(TableStyle(style))
    story.append(totals_table)
    if document.discount_reason:
        story += [Spacer(1, 2 * mm), _p(f"Discount: {document.discount_reason}", small)]

    # Payments and refunds.
    def _ledger(
        title: str, heads: tuple[str, ...], entries: tuple[tuple[str, str, str, str], ...]
    ) -> None:
        if not entries:
            return
        story.append(Spacer(1, 7 * mm))
        story.append(_p(title, _style(10, bold=True)))
        story.append(Spacer(1, 1.5 * mm))
        data = [
            [_p(h, label) for h in heads[:3]]
            + [Paragraph(heads[3], _style(8, bold=True, color=_MUTED, align=TA_RIGHT))]
        ]
        data += [[_p(a, body), _p(b, body), _p(c, body), _p(d, right)] for a, b, c, d in entries]
        table = Table(data, colWidths=[width * f for f in (0.18, 0.18, 0.44, 0.2)])
        table.setStyle(
            TableStyle(
                [
                    ("LINEBELOW", (0, 0), (-1, 0), 0.6, _INK),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.4, _RULE),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    _ledger("Payments", ("Date", "Method", "Reference", "Amount"), document.payments)
    _ledger("Refunds", ("Date", "Method", "Reason", "Amount"), document.refunds)

    if document.notes:
        story += [Spacer(1, 7 * mm), _p("Notes", _style(10, bold=True)), _p(document.notes, body)]
    if document.void_reason:
        story += [
            Spacer(1, 7 * mm),
            _p("Voided", _style(10, bold=True)),
            _p(document.void_reason, body),
        ]

    footer = (
        f"Computer-generated invoice {document.invoice_number} · {head.name} · "
        f"Generated {document.generated_at}"
    )

    def _decorate(canvas: Canvas, doc: BaseDocTemplate) -> None:
        canvas.saveState()
        canvas.setFont(_REGULAR, 7.5)
        canvas.setFillColor(_MUTED)
        canvas.drawString(margin, 10 * mm, footer)
        canvas.drawRightString(A4[0] - margin, 10 * mm, f"Page {doc.page}")
        if document.status_stamp == "VOID":
            canvas.setFont(_BOLD, 90)
            canvas.setFillColor(colors.Color(0.71, 0.14, 0.09, alpha=0.12))
            canvas.translate(A4[0] / 2, A4[1] / 2)
            canvas.rotate(35)
            canvas.drawCentredString(0, 0, "VOID")
        canvas.restoreState()

    pdf.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    return buffer.getvalue()
