# ruff: noqa: F811 — fixtures imported from the lab tests are requested by name
"""API tests for ``GET /api/v1/lab-orders/{id}/report.pdf`` (``docs/modules/07-laboratory.md`` §9).

Real app, service, repository and database. What the report says is tested in
``app/tests/unit/services/test_lab_report_pdf.py``; here: who may download it,
which orders have one, and that what comes back is a PDF.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from app.tests.api.test_lab_api import (  # noqa: F401 — fixtures, registered by import
    ORDERS,
    _enter,
    _order,
    _post,
    _released,
    admin,
    api,
    appointment,
    audit,
    doctor,
    other_tenant,
    tests,
)
from app.tests.billing_helpers import auth_headers, insert_user_with_permissions

if TYPE_CHECKING:
    from httpx import AsyncClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.appointment import Appointment

pytestmark = pytest.mark.database


def _report(order_id: str) -> str:
    return f"{ORDERS}/{order_id}/report.pdf"


@pytest_asyncio.fixture
async def downloader(db_session: AsyncSession, hospital_id: uuid.UUID) -> dict[str, str]:
    """Reads lab orders and downloads their reports."""
    user = await insert_user_with_permissions(
        db_session, hospital_id, ["lab.order.read", "lab.report.download"]
    )
    return auth_headers(user.id, hospital_id)


class TestDownload:
    async def test_a_released_order_is_a_pdf(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        downloader: dict[str, str],
        appointment: Appointment,
        tests: dict[str, str],
    ) -> None:
        order = await _released(api, admin, appointment, tests, K="6.9", HB="13.0")

        response = await api.get(_report(order["id"]), headers=downloader)

        assert response.status_code == 200, response.text
        assert response.headers["content-type"] == "application/pdf"
        disposition = response.headers["content-disposition"]
        assert disposition.startswith('attachment; filename="lab-report-')
        assert disposition.endswith('.pdf"')
        assert response.headers["cache-control"] == "no-store"
        assert response.content.startswith(b"%PDF-")
        assert response.content.rstrip().endswith(b"%%EOF")

    async def test_an_order_with_results_not_yet_released_has_no_report(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        downloader: dict[str, str],
        appointment: Appointment,
        tests: dict[str, str],
    ) -> None:
        order = await _order(api, admin, appointment, tests)
        await _post(api, admin, order, "collect")
        await _enter(api, admin, order, K="4.2", HB="13.0")

        response = await api.get(_report(order["id"]), headers=downloader)

        assert response.status_code == 400
        assert response.json()["error_code"] == "BUSINESS_RULE_VIOLATION"

    async def test_a_fresh_order_has_no_report(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        downloader: dict[str, str],
        appointment: Appointment,
        tests: dict[str, str],
    ) -> None:
        order = await _order(api, admin, appointment, tests)

        response = await api.get(_report(order["id"]), headers=downloader)

        assert response.status_code == 400


class TestWhoMayDownload:
    async def test_reading_orders_is_not_enough(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        db_session: AsyncSession,
        hospital_id: uuid.UUID,
        appointment: Appointment,
        tests: dict[str, str],
    ) -> None:
        order = await _released(api, admin, appointment, tests)
        reader = await insert_user_with_permissions(db_session, hospital_id, ["lab.order.read"])

        response = await api.get(_report(order["id"]), headers=auth_headers(reader.id, hospital_id))

        assert response.status_code == 403

    async def test_no_token_is_unauthorised(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        appointment: Appointment,
        tests: dict[str, str],
    ) -> None:
        order = await _released(api, admin, appointment, tests)

        response = await api.get(_report(order["id"]))

        assert response.status_code == 401

    async def test_another_hospital_cannot_see_it(
        self,
        api: AsyncClient,
        admin: dict[str, str],
        other_tenant: dict[str, str],
        db_session: AsyncSession,
        other_hospital_id: uuid.UUID,
        appointment: Appointment,
        tests: dict[str, str],
    ) -> None:
        order = await _released(api, admin, appointment, tests)
        outsider = await insert_user_with_permissions(
            db_session, other_hospital_id, ["lab.order.read", "lab.report.download"]
        )

        response = await api.get(
            _report(order["id"]), headers=auth_headers(outsider.id, other_hospital_id)
        )

        assert response.status_code == 404

    async def test_an_unknown_order_is_not_found(
        self, api: AsyncClient, downloader: dict[str, str]
    ) -> None:
        response = await api.get(_report(str(uuid.uuid4())), headers=downloader)

        assert response.status_code == 404
