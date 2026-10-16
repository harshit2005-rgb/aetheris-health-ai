"""Lab report PDFs (``docs/modules/07-laboratory.md`` §9 ``report.pdf``, FR-5, AC-4).

Like invoices, two steps:

1. :func:`build_lab_report` turns a released order, exactly as
   ``GET /lab-orders/{id}`` returns it, into a :class:`LabReportDocument`:
   every string the PDF shows. Values, units, reference bounds and flags are
   the order's own, so the PDF matches the screen value for value (AC-4).
2. :func:`render_lab_report_pdf` lays it out on A4 with the hospital's
   letterhead (FR-5).

**Only released results are printed.** A report is what leaves the lab; an
order still in progress has no report (module spec §4 rule 3).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final
from zoneinfo import ZoneInfo

from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import mm
from reportlab.platypus import Spacer, Table, TableStyle

from app.models.lab import LabOrderStatus, LabResultFlag
from app.services.pdf_layout import (
    ALERT,
    CONTENT_WIDTH,
    INK,
    MUTED,
    RULE,
    Letterhead,
    PageSpec,
    age_and_sex,
    header_block,
    meta_block,
    para,
    render_pages,
    style,
)

if TYPE_CHECKING:
    from datetime import date, datetime
    from decimal import Decimal

    from app.schemas.lab import LabOrderItemResponse, LabOrderResponse

__all__ = ["LabReportDocument", "LabReportLine", "build_lab_report", "render_lab_report_pdf"]

_FLAG_LABEL: Final = {
    LabResultFlag.NORMAL: "",
    LabResultFlag.LOW: "LOW",
    LabResultFlag.HIGH: "HIGH",
    LabResultFlag.CRITICAL: "CRITICAL",
}

_PRIORITY_LABEL: Final = {"routine": "Routine", "urgent": "Urgent", "stat": "STAT"}


@dataclass(frozen=True, slots=True)
class LabReportLine:
    """One test on the report, formatted."""

    test: str
    result: str
    unit: str
    reference: str
    flag: str
    amended: bool
    note: str | None


@dataclass(frozen=True, slots=True)
class LabReportDocument:
    """Every string a lab report shows. Built by :func:`build_lab_report`."""

    letterhead: Letterhead
    report_number: str
    patient_name: str
    patient_mrn: str
    age_sex: str
    doctor_name: str
    priority: str
    ordered_on: str
    collected_on: str
    released_on: str
    lines: tuple[LabReportLine, ...]
    has_critical: bool
    notes: str | None
    generated_at: str


def _number(value: Decimal) -> str:
    """A bound without trailing zeros: 4.5, 11, 0.04."""
    return f"{value.normalize():f}"


def _reference(item: LabOrderItemResponse) -> str:
    """The range the flag was judged against, as the lab writes it."""
    low, high = item.reference_low, item.reference_high
    if low is not None and high is not None:
        return f"{_number(low)} – {_number(high)}"
    if high is not None:
        return f"< {_number(high)}"
    if low is not None:
        return f"> {_number(low)}"
    return "—"


def _moment(moment: datetime | None, zone: ZoneInfo) -> str:
    return moment.astimezone(zone).strftime("%d %b %Y, %H:%M") if moment else "—"


def build_lab_report(
    order: LabOrderResponse,
    *,
    letterhead: Letterhead,
    date_of_birth: date | None,
    sex: str | None,
    generated_at: datetime,
) -> LabReportDocument:
    """Everything the report shows, from the order exactly as the API returns it.

    :param order: The order DTO. It must be released.
    :param letterhead: The hospital's letterhead.
    :param date_of_birth: The patient's date of birth, for the age.
    :param sex: The patient's recorded gender.
    :param generated_at: When the PDF is made (UTC).
    :returns: The document.
    :raises ValueError: If the order is not released.
    """
    if order.status is not LabOrderStatus.RELEASED or order.released_at is None:
        msg = "Only a released lab order has a report."
        raise ValueError(msg)
    zone = ZoneInfo(letterhead.timezone)
    collected_at = order.collected_at or min(
        (i.sample_collected_at for i in order.items if i.sample_collected_at), default=None
    )
    lines = tuple(
        LabReportLine(
            test=item.test_name,
            result=item.result_value or "—",
            unit=item.result_unit or "",
            reference=_reference(item),
            flag=_FLAG_LABEL.get(item.result_flag, "") if item.result_flag else "",
            amended=bool(item.amendments),
            note=item.notes,
        )
        for item in order.items
    )
    return LabReportDocument(
        letterhead=letterhead,
        report_number=f"LAB-{str(order.id)[:8].upper()}",
        patient_name=order.patient_name,
        patient_mrn=order.patient_mrn,
        age_sex=age_and_sex(date_of_birth, sex, on=order.released_at.astimezone(zone).date()),
        doctor_name=order.doctor_name,
        priority=_PRIORITY_LABEL.get(order.priority.value, order.priority.value),
        ordered_on=_moment(order.ordered_at, zone),
        collected_on=_moment(collected_at, zone),
        released_on=_moment(order.released_at, zone),
        lines=lines,
        has_critical=order.has_critical,
        notes=order.notes,
        generated_at=generated_at.astimezone(zone).strftime("%d %b %Y, %H:%M")
        + f" ({letterhead.timezone})",
    )


def render_lab_report_pdf(document: LabReportDocument) -> bytes:
    """Lay the report out on A4 and return the PDF.

    :param document: What to print.
    :returns: The PDF file's bytes.
    """
    body = style(9)
    bold = style(9, bold=True)
    alert = style(9, bold=True, color=ALERT)
    small = style(7.5, color=MUTED)
    label = style(8, bold=True, color=MUTED)

    story: list[Any] = [
        header_block(document.letterhead, "LABORATORY REPORT"),
        Spacer(1, 5 * mm),
        meta_block(
            [
                ("Patient", document.patient_name),
                ("MRN", document.patient_mrn),
                ("Age / Sex", document.age_sex),
                ("Report no.", document.report_number),
                ("Referred by", document.doctor_name),
                ("Priority", document.priority),
                ("Sample collected", document.collected_on),
                ("Reported", document.released_on),
            ]
        ),
        Spacer(1, 6 * mm),
    ]
    if document.has_critical:
        story += [
            para("CRITICAL VALUES PRESENT — please review urgently.", alert),
            Spacer(1, 3 * mm),
        ]

    heads = ("Test", "Result", "Unit", "Reference range", "Flag")
    rows: list[list[Any]] = [[para(h, label) for h in heads]]
    for line in document.lines:
        test_cell: list[Any] = [para(line.test, body)]
        if line.amended:
            test_cell.append(para("Amended after release", small))
        if line.note:
            test_cell.append(para(line.note, small))
        is_flagged = bool(line.flag)
        rows.append(
            [
                test_cell,
                para(line.result, alert if is_flagged else bold),
                para(line.unit, body),
                para(line.reference, body),
                para(line.flag, alert),
            ]
        )
    table = Table(
        rows,
        colWidths=[CONTENT_WIDTH * f for f in (0.36, 0.17, 0.12, 0.23, 0.12)],
        repeatRows=1,
    )
    table_style: list[tuple[Any, ...]] = [
        ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    table.setStyle(TableStyle(table_style))
    story += [table, Spacer(1, 4 * mm)]
    story.append(
        para(
            "Values outside the reference range are marked LOW, HIGH or CRITICAL. "
            "Results relate only to the samples tested.",
            small,
        )
    )
    if document.notes:
        story += [Spacer(1, 5 * mm), para("Clinical notes", style(10, bold=True))]
        story.append(para(document.notes, body))

    signature = Table(
        [
            [para("", body), para("Authorised signatory", style(8, color=MUTED, align=TA_RIGHT))],
            [para("", body), para("Laboratory", style(9, bold=True, align=TA_RIGHT))],
        ],
        colWidths=[CONTENT_WIDTH * 0.6, CONTENT_WIDTH * 0.4],
    )
    signature.setStyle(TableStyle([("LINEABOVE", (1, 0), (1, 0), 0.6, INK)]))
    story += [Spacer(1, 18 * mm), signature]

    footer = (
        f"Lab report {document.report_number} · {document.letterhead.name} · "
        f"Generated {document.generated_at}"
    )
    return render_pages(
        story,
        PageSpec(
            title=f"Lab report {document.report_number}",
            author=document.letterhead.name,
            footer=footer,
        ),
    )
