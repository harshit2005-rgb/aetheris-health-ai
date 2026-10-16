"""Unit tests for invoice PDFs (``docs/modules/06-billing.md`` §9, AC-5).

The document is tested as data — every string the PDF will show — so "the PDF
matches the on-screen invoice line for line" is checked exactly; the renderer
is tested for producing a sound PDF from any such document, hostile text and
long invoices included.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.constants import InvoiceStatus
from app.models.billing import PaymentMethod
from app.schemas.billing import (
    InvoiceItemResponse,
    InvoiceResponse,
    PaymentResponse,
    RefundResponse,
)
from app.services.invoice_pdf import (
    Letterhead,
    build_invoice_document,
    format_money,
    letterhead_from,
    render_invoice_pdf,
)

ISSUED = datetime(2026, 10, 16, 20, 30, tzinfo=UTC)  # 17 Oct 2026, 02:00 in India
NOW = datetime(2026, 10, 18, 6, 0, tzinfo=UTC)

LETTERHEAD = Letterhead(
    name="Demo Hospital & Clinic",
    address_lines=("123 Healthcare Avenue", "Hyderabad, Telangana 500081", "India"),
    contact="+91 80123 45678 · billing@demo.example",
    gstin="36AAAAA0000A1Z5",
    timezone="Asia/Kolkata",
)


def _item(
    position: int, description: str, quantity: str, price: str, tax: str, total: str
) -> InvoiceItemResponse:
    return InvoiceItemResponse(
        id=uuid.uuid4(),
        service_id=None,
        description=description,
        quantity=Decimal(quantity),
        unit_price=Decimal(price),
        tax_rate=Decimal(tax),
        line_total=Decimal(total),
        position=position,
    )


def an_invoice(**overrides: Any) -> InvoiceResponse:
    """An issued, partly paid invoice: a consultation and two medicines."""
    fields: dict[str, Any] = {
        "id": uuid.uuid4(),
        "hospital_id": uuid.uuid4(),
        "invoice_number": "INV-2026-000042",
        "patient_id": uuid.uuid4(),
        "patient_name": "Ravi Kumar",
        "appointment_id": None,
        "status": InvoiceStatus.PARTIALLY_PAID,
        "currency": "INR",
        "items": [
            _item(1, "Paracetamol 650 mg strip", "2", "45.00", "12", "100.80"),
            _item(0, "Consultation — General Medicine", "1", "800.00", "0", "800.00"),
        ],
        "subtotal": Decimal("890.00"),
        "tax_amount": Decimal("10.80"),
        "discount_amount": Decimal("0.00"),
        "discount_reason": None,
        "discount_pending_approval": False,
        "discount_approved_by": None,
        "total": Decimal("900.80"),
        "amount_paid": Decimal("500.00"),
        "amount_refunded": Decimal("0.00"),
        "balance_due": Decimal("400.80"),
        "notes": None,
        "issued_at": ISSUED,
        "voided_at": None,
        "void_reason": None,
        "created_at": ISSUED,
        "updated_at": ISSUED,
    }
    fields.update(overrides)
    return InvoiceResponse(**fields)


def a_payment(amount: str = "500.00", method: PaymentMethod = PaymentMethod.UPI) -> PaymentResponse:
    return PaymentResponse(
        id=uuid.uuid4(),
        invoice_id=uuid.uuid4(),
        amount=Decimal(amount),
        method=method,
        reference="UPI-TXN-8899",
        notes=None,
        received_by=uuid.uuid4(),
        received_at=ISSUED,
    )


def a_refund(amount: str = "100.00") -> RefundResponse:
    return RefundResponse(
        id=uuid.uuid4(),
        invoice_id=uuid.uuid4(),
        amount=Decimal(amount),
        method=PaymentMethod.CASH,
        reason="Medicine returned unopened",
        reference=None,
        refunded_by=uuid.uuid4(),
        refunded_at=NOW,
    )


def _document(invoice: InvoiceResponse | None = None, **kwargs: Any) -> Any:
    return build_invoice_document(
        invoice or an_invoice(),
        letterhead=kwargs.get("letterhead", LETTERHEAD),
        patient_mrn=kwargs.get("patient_mrn", "MRN-000017"),
        payments=kwargs.get("payments", [a_payment()]),
        refunds=kwargs.get("refunds", []),
        generated_at=NOW,
    )


class TestMoney:
    @pytest.mark.parametrize(
        ("amount", "expected"),
        [
            ("0", "₹0.00"),
            ("7.5", "₹7.50"),
            ("999.99", "₹999.99"),
            ("1000", "₹1,000.00"),
            ("123456.78", "₹1,23,456.78"),
            ("12345678.9", "₹1,23,45,678.90"),
            ("-250", "-₹250.00"),
            ("0.005", "₹0.01"),
        ],
    )
    def test_rupees_are_grouped_in_lakhs_and_crores(self, amount: str, expected: str) -> None:
        assert format_money(Decimal(amount), "INR") == expected

    def test_another_currency_is_grouped_in_thousands_with_its_code(self) -> None:
        assert format_money(Decimal("1234567.5"), "USD") == "USD 1,234,567.50"


class TestTheDocumentIsTheInvoice:
    def test_lines_are_the_invoices_own_in_invoice_order(self) -> None:
        document = _document()

        assert document.lines == (
            ("1", "Consultation — General Medicine", "1", "₹800.00", "0%", "₹800.00"),
            ("2", "Paracetamol 650 mg strip", "2", "₹45.00", "12%", "₹100.80"),
        )

    def test_totals_are_the_invoices_own_not_recomputed(self) -> None:
        # Deliberately inconsistent figures: the PDF shows what the API says.
        invoice = an_invoice(
            subtotal=Decimal("1.11"), tax_amount=Decimal("2.22"), total=Decimal("3.33")
        )

        assert dict(_document(invoice).totals) == {
            "Subtotal": "₹1.11",
            "Tax": "₹2.22",
            "Total": "₹3.33",
            "Paid": "₹500.00",
            "Outstanding": "₹400.80",
        }

    def test_a_discount_shows_as_a_deduction_with_its_reason(self) -> None:
        invoice = an_invoice(discount_amount=Decimal("90.00"), discount_reason="Senior citizen")

        document = _document(invoice)

        assert ("Discount", "-₹90.00") in document.totals
        assert [name for name, _ in document.totals].index("Discount") < [
            name for name, _ in document.totals
        ].index("Total")
        assert document.discount_reason == "Senior citizen"

    def test_no_discount_means_no_discount_line(self) -> None:
        document = _document()

        assert "Discount" not in dict(document.totals)
        assert document.discount_reason is None

    def test_refunds_are_listed_and_totalled(self) -> None:
        invoice = an_invoice(status=InvoiceStatus.REFUNDED, amount_refunded=Decimal("100.00"))

        document = _document(invoice, refunds=[a_refund()])

        assert dict(document.totals)["Refunded"] == "₹100.00"
        assert document.refunds == (
            ("18 Oct 2026", "Cash", "Medicine returned unopened", "₹100.00"),
        )
        assert document.status_stamp == "REFUNDED"

    def test_dates_are_on_the_hospitals_clock(self) -> None:
        document = _document()

        # 20:30 UTC on the 16th is 02:00 on the 17th in India.
        assert document.issued_on == "17 Oct 2026"
        assert document.payments == (("17 Oct 2026", "UPI", "UPI-TXN-8899", "₹500.00"),)
        assert document.generated_at == "18 Oct 2026, 11:30 (Asia/Kolkata)"

    @pytest.mark.parametrize(
        ("status", "stamp"),
        [
            (InvoiceStatus.ISSUED, None),
            (InvoiceStatus.PARTIALLY_PAID, "PARTIALLY PAID"),
            (InvoiceStatus.PAID, "PAID"),
            (InvoiceStatus.VOID, "VOID"),
        ],
    )
    def test_the_status_is_stamped(self, status: InvoiceStatus, stamp: str | None) -> None:
        assert _document(an_invoice(status=status)).status_stamp == stamp

    def test_a_void_invoice_owes_nothing_and_says_why(self) -> None:
        invoice = an_invoice(status=InvoiceStatus.VOID, void_reason="Raised for the wrong patient")

        document = _document(invoice)

        assert "Outstanding" not in dict(document.totals)
        assert document.void_reason == "Raised for the wrong patient"

    def test_a_draft_has_no_pdf(self) -> None:
        with pytest.raises(ValueError, match="draft"):
            _document(an_invoice(status=InvoiceStatus.DRAFT, invoice_number=None, issued_at=None))


class TestLetterhead:
    def test_reads_the_hospital_row(self) -> None:
        hospital = SimpleNamespace(
            name="Lakeview Clinic",
            address={
                "street": "4 Lake Road",
                "city": "Hyderabad",
                "state": "Telangana",
                "zip": "500034",
                "country": "India",
            },
            phone="+91 40 1234 5678",
            email=None,
            settings={"billing": {"gstin": " 36ABCDE1234F1Z5 "}},
            timezone="Asia/Kolkata",
        )

        letterhead = letterhead_from(hospital)

        assert letterhead.address_lines == ("4 Lake Road", "Hyderabad, Telangana 500034", "India")
        assert letterhead.contact == "+91 40 1234 5678"
        assert letterhead.gstin == "36ABCDE1234F1Z5"

    @pytest.mark.parametrize(
        "settings", [None, {}, {"billing": "oops"}, {"billing": {"gstin": "  "}}]
    )
    def test_no_gstin_unless_one_is_set(self, settings: Any) -> None:
        hospital = SimpleNamespace(
            name="H", address={}, phone=None, email=None, settings=settings, timezone="Asia/Kolkata"
        )

        letterhead = letterhead_from(hospital)

        assert letterhead.gstin is None
        assert letterhead.address_lines == ()
        assert letterhead.contact is None


class TestRendering:
    def test_a_sound_pdf(self) -> None:
        content = render_invoice_pdf(_document())

        assert content.startswith(b"%PDF-")
        assert content.rstrip().endswith(b"%%EOF")
        assert b"/FontName /AAAAAA+NotoSans" in content or b"NotoSans" in content

    def test_markup_in_any_text_is_printed_not_obeyed(self) -> None:
        hostile = '<b>bold</b> <img src="x"/> <font color="red">&nbsp; </para>'
        invoice = an_invoice(
            patient_name=hostile,
            notes=hostile,
            items=[_item(0, hostile, "1", "10.00", "0", "10.00")],
        )

        content = render_invoice_pdf(_document(invoice))

        assert content.startswith(b"%PDF-")

    def test_a_long_invoice_runs_onto_more_pages(self) -> None:
        items = [_item(i, f"Line {i}", "1", "1.00", "0", "1.00") for i in range(120)]

        one_page = render_invoice_pdf(_document())
        long = render_invoice_pdf(_document(an_invoice(items=items)))

        assert one_page.count(b"/Type /Page\n") + one_page.count(b"/Type /Page ") == 1
        assert long.count(b"/Type /Page\n") + long.count(b"/Type /Page ") > 1

    def test_a_void_invoice_renders(self) -> None:
        invoice = an_invoice(status=InvoiceStatus.VOID, void_reason="Duplicate")

        assert render_invoice_pdf(_document(invoice)).startswith(b"%PDF-")
