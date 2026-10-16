# ruff: noqa: F811 — fixtures imported from the invoice tests are requested by name
"""API tests for ``GET /api/v1/invoices/{id}/pdf`` (``docs/modules/06-billing.md`` §9).

Real app, service, repository and database. What the PDF says is tested in
``app/tests/unit/services/test_invoice_pdf.py``; here: who may download which
invoice, and that what comes back is a PDF of that invoice.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio

from app.tests.api.test_invoices_api import (  # noqa: F401 — fixtures, registered by import
    ALL_BILLING_PERMISSIONS,
    URL,
    _draft,
    _issued,
    _pay,
    admin,
    api,
    audit,
    other_tenant,
    patient_id,
)
from app.tests.billing_helpers import (
    auth_headers,
    insert_appointment,
    insert_doctor,
    insert_user_with_permissions,
)

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.database

DOWNLOAD = [*ALL_BILLING_PERMISSIONS, "invoice.pdf.download"]


def _pdf(invoice_id: str) -> str:
    return f"{URL}/{invoice_id}/pdf"


@pytest_asyncio.fixture
async def cashier(db_session: AsyncSession, hospital_id: uuid.UUID) -> dict[str, str]:
    """Reads invoices and downloads their PDFs."""
    user = await insert_user_with_permissions(
        db_session, hospital_id, ["invoice.read", "invoice.pdf.download"]
    )
    return auth_headers(user.id, hospital_id)


class TestDownload:
    async def test_an_issued_invoice_is_a_pdf_named_by_its_number(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        cashier: dict[str, str],
        patient_id: uuid.UUID,
    ) -> None:
        invoice = await _issued(api, admin, patient_id)
        assert (await _pay(api, admin, invoice["id"], "200.00")).status_code == 201

        response = await api.get(_pdf(invoice["id"]), headers=cashier)

        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        number = invoice["invoice_number"]
        assert (
            response.headers["content-disposition"]
            == f'attachment; filename="invoice-{number}.pdf"'
        )
        assert response.headers["cache-control"] == "no-store"
        assert response.content.startswith(b"%PDF-")
        assert response.content.rstrip().endswith(b"%%EOF")

    async def test_a_void_invoice_still_has_a_pdf(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        cashier: dict[str, str],
        patient_id: uuid.UUID,
    ) -> None:
        invoice = await _issued(api, admin, patient_id)
        voided = await api.post(
            f"{URL}/{invoice['id']}/void", json={"reason": "Raised in error"}, headers=admin
        )
        assert voided.status_code == 200, voided.text

        response = await api.get(_pdf(invoice["id"]), headers=cashier)

        assert response.status_code == 200, response.text
        assert response.content.startswith(b"%PDF-")

    async def test_a_draft_has_no_pdf(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        cashier: dict[str, str],
        patient_id: uuid.UUID,
    ) -> None:
        draft = await _draft(api, admin, patient_id)

        response = await api.get(_pdf(draft["id"]), headers=cashier)

        assert response.status_code == 400
        body = response.json()
        assert body["error_code"] == "BUSINESS_RULE_VIOLATION"
        assert "Issue it first." in body["message"]


class TestWhoMayDownload:
    async def test_reading_an_invoice_is_not_enough(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> None:
        reader = await insert_user_with_permissions(db_session, hospital_id, ["invoice.read"])
        invoice = await _issued(api, admin, patient_id)

        response = await api.get(_pdf(invoice["id"]), headers=auth_headers(reader.id, hospital_id))

        assert response.status_code == 403

    async def test_no_token_is_401(
        self, api: AsyncClient, admin: dict[str, str], patient_id: uuid.UUID
    ) -> None:
        invoice = await _issued(api, admin, patient_id)

        response = await api.get(_pdf(invoice["id"]))

        assert response.status_code == 401

    async def test_another_hospitals_invoice_is_not_found(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        db_session: AsyncSession,
        other_hospital_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> None:
        invoice = await _issued(api, admin, patient_id)
        stranger = await insert_user_with_permissions(db_session, other_hospital_id, DOWNLOAD)

        response = await api.get(
            _pdf(invoice["id"]), headers=auth_headers(stranger.id, other_hospital_id)
        )

        assert response.status_code == 404

    async def test_an_unknown_invoice_is_not_found(
        self, api: AsyncClient, cashier: dict[str, str]
    ) -> None:
        response = await api.get(_pdf(str(uuid.uuid4())), headers=cashier)

        assert response.status_code == 404

    async def test_a_doctor_downloads_only_their_own_visits(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        patient_id: uuid.UUID,
    ) -> None:
        user = await insert_user_with_permissions(
            db_session, hospital_id, ["invoice.read.own", "invoice.pdf.download"]
        )
        me = await insert_doctor(db_session, hospital_id, user_id=user.id)
        colleague = await insert_doctor(db_session, hospital_id)
        mine = await insert_appointment(
            db_session, hospital_id, patient_id=patient_id, doctor_id=me.id
        )
        theirs = await insert_appointment(
            db_session, hospital_id, patient_id=patient_id, doctor_id=colleague.id
        )
        my_invoice = await _issued(api, admin, patient_id, appointment_id=str(mine.id))
        their_invoice = await _issued(api, admin, patient_id, appointment_id=str(theirs.id))
        doctor: dict[str, Any] = auth_headers(user.id, hospital_id)

        assert (await api.get(_pdf(my_invoice["id"]), headers=doctor)).status_code == 200
        assert (await api.get(_pdf(their_invoice["id"]), headers=doctor)).status_code == 404
