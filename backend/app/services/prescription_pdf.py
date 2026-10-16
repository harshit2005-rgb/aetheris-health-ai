"""Prescription PDFs: the slip a patient carries out of the consultation.

Built from a prescription exactly as ``GET /prescriptions/{id}`` returns it,
on the hospital's letterhead, with the prescribing doctor's name,
specialisation and registration number, the medicines with dosage, frequency,
duration and instructions, and a signature line.

A cancelled prescription still prints, watermarked CANCELLED with the reason,
so the record can be shown; it must not be dispensed from.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.units import mm
from reportlab.platypus import Spacer, Table, TableStyle

from app.models.pharmacy import PrescriptionStatus
from app.services.pdf_layout import (
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

    from app.schemas.pharmacy import PrescriptionResponse

__all__ = [
    "PrescriptionDocument",
    "PrescriptionLine",
    "build_prescription_document",
    "render_prescription_pdf",
]


@dataclass(frozen=True, slots=True)
class PrescriptionLine:
    """One medicine on the slip, formatted."""

    medicine: str
    dosage: str
    frequency: str
    duration: str
    quantity: str
    instructions: str | None


@dataclass(frozen=True, slots=True)
class PrescriptionDocument:
    """Every string a prescription PDF shows."""

    letterhead: Letterhead
    reference: str
    patient_name: str
    patient_mrn: str
    age_sex: str
    doctor_name: str
    doctor_specialization: str | None
    doctor_registration: str | None
    prescribed_on: str
    lines: tuple[PrescriptionLine, ...]
    notes: str | None
    cancelled_reason: str | None
    generated_at: str


def _duration(days: int | None) -> str:
    if days is None:
        return "—"
    return "1 day" if days == 1 else f"{days} days"


def build_prescription_document(
    prescription: PrescriptionResponse,
    *,
    letterhead: Letterhead,
    date_of_birth: date | None,
    sex: str | None,
    doctor_specialization: str | None,
    doctor_registration: str | None,
    generated_at: datetime,
) -> PrescriptionDocument:
    """Everything the slip shows, from the prescription as the API returns it.

    :param prescription: The prescription DTO.
    :param letterhead: The hospital's letterhead.
    :param date_of_birth: The patient's date of birth, for the age.
    :param sex: The patient's recorded gender.
    :param doctor_specialization: The prescriber's specialisation.
    :param doctor_registration: The prescriber's medical registration number.
    :param generated_at: When the PDF is made (UTC).
    :returns: The document.
    """
    zone = ZoneInfo(letterhead.timezone)
    prescribed = prescription.prescribed_at.astimezone(zone)
    return PrescriptionDocument(
        letterhead=letterhead,
        reference=f"RX-{str(prescription.id)[:8].upper()}",
        patient_name=prescription.patient_name,
        patient_mrn=prescription.patient_mrn,
        age_sex=age_and_sex(date_of_birth, sex, on=prescribed.date()),
        doctor_name=prescription.doctor_name,
        doctor_specialization=doctor_specialization or None,
        doctor_registration=doctor_registration or None,
        prescribed_on=prescribed.strftime("%d %b %Y, %H:%M"),
        lines=tuple(
            PrescriptionLine(
                medicine=item.medicine_name,
                dosage=item.dosage,
                frequency=item.frequency,
                duration=_duration(item.duration_days),
                quantity=str(item.quantity),
                instructions=item.instructions,
            )
            for item in prescription.items
        ),
        notes=prescription.notes,
        cancelled_reason=(
            prescription.cancel_reason or "Cancelled"
            if prescription.status is PrescriptionStatus.CANCELLED
            else None
        ),
        generated_at=generated_at.astimezone(zone).strftime("%d %b %Y, %H:%M")
        + f" ({letterhead.timezone})",
    )


def render_prescription_pdf(document: PrescriptionDocument) -> bytes:
    """Lay the prescription out on A4 and return the PDF.

    :param document: What to print.
    :returns: The PDF file's bytes.
    """
    body = style(9)
    bold = style(9.5, bold=True)
    small = style(7.5, color=MUTED)
    label = style(8, bold=True, color=MUTED)

    # The API already names a doctor "Dr. First Last".
    doctor_line = document.doctor_name
    meta: list[tuple[str, str]] = [
        ("Patient", document.patient_name),
        ("MRN", document.patient_mrn),
        ("Age / Sex", document.age_sex),
        ("Date", document.prescribed_on),
        ("Doctor", doctor_line),
        ("Specialisation", document.doctor_specialization or "—"),
        ("Reg. no.", document.doctor_registration or "—"),
        ("Reference", document.reference),
    ]
    story: list[Any] = [
        header_block(
            document.letterhead,
            "PRESCRIPTION",
            stamp="CANCELLED" if document.cancelled_reason else None,
        ),
        Spacer(1, 5 * mm),
        meta_block(meta),
        Spacer(1, 6 * mm),
        para("Rx", style(18, bold=True)),
        Spacer(1, 2 * mm),
    ]

    heads = ("#", "Medicine", "Dose", "Frequency", "Duration", "Qty")
    rows: list[list[Any]] = [[para(h, label) for h in heads]]
    for index, line in enumerate(document.lines, start=1):
        medicine: list[Any] = [para(line.medicine, bold)]
        if line.instructions:
            medicine.append(para(line.instructions, small))
        rows.append(
            [
                para(str(index), body),
                medicine,
                para(line.dosage, body),
                para(line.frequency, body),
                para(line.duration, body),
                para(line.quantity, style(9, align=TA_RIGHT)),
            ]
        )
    table = Table(
        rows,
        colWidths=[CONTENT_WIDTH * f for f in (0.05, 0.39, 0.15, 0.17, 0.13, 0.11)],
        repeatRows=1,
    )
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (0, 0), (-1, 0), 0.8, INK),
                ("LINEBELOW", (0, 1), (-1, -1), 0.4, RULE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    story.append(table)
    if document.notes:
        story += [
            Spacer(1, 6 * mm),
            para("Advice", style(10, bold=True)),
            para(document.notes, body),
        ]
    if document.cancelled_reason:
        story += [
            Spacer(1, 6 * mm),
            para("Cancelled — do not dispense", style(10, bold=True)),
            para(document.cancelled_reason, body),
        ]

    sign_lines: list[Any] = [para(doctor_line, style(9.5, bold=True, align=TA_RIGHT))]
    if document.doctor_registration:
        sign_lines.append(
            para(f"Reg. no. {document.doctor_registration}", style(8, color=MUTED, align=TA_RIGHT))
        )
    signature = Table(
        [
            [para("", body), para("Signature", style(8, color=MUTED, align=TA_RIGHT))],
            [para("", body), sign_lines],
        ],
        colWidths=[CONTENT_WIDTH * 0.6, CONTENT_WIDTH * 0.4],
    )
    signature.setStyle(TableStyle([("LINEABOVE", (1, 0), (1, 0), 0.6, INK)]))
    story += [Spacer(1, 20 * mm), signature]

    footer = (
        f"Prescription {document.reference} · {document.letterhead.name} · "
        f"Generated {document.generated_at}"
    )
    return render_pages(
        story,
        PageSpec(
            title=f"Prescription {document.reference}",
            author=document.letterhead.name,
            footer=footer,
            watermark="CANCELLED" if document.cancelled_reason else None,
        ),
    )
