"""End-to-end notification flows.

Each test starts with the thing a person does in another module — invites a
colleague, asks for a password reset, applies a discount — and follows it to
what the recipient ends up with: an entry in their notification centre and,
where the kind calls for one, an email that the worker sends.

Real app, real database. The only thing faked is the SMTP server.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.api.dependencies.db import get_db_session
from app.api.dependencies.services import get_audit_sink
from app.main import create_app
from app.models.hospital import Hospital
from app.models.notification import DeliveryStatus, Notification, NotificationDelivery
from app.models.user import User, UserStatus
from app.repositories.hospital_repository import HospitalRepository
from app.repositories.notification_repository import NotificationRepository
from app.repositories.user_repository import UserRepository
from app.services.notification_service import NotificationService
from app.tests.billing_helpers import auth_headers, insert_patient, insert_user_with_permissions
from app.tests.conftest import RecordingAuditSink

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator

    from fastapi import FastAPI
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.email import EmailMessage

pytestmark = pytest.mark.database

NOTIFICATIONS = "/api/v1/notifications"
OWN = ["notification.read.own", "notification.preference.update.own"]
PASSWORD = "Str0ng!Passw0rd123"  # noqa: S105 — a test credential, not a real one


class _Outbox:
    """A stand-in SMTP server that keeps what it was asked to send."""

    def __init__(self) -> None:
        self.messages: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.messages.append(message)


@pytest_asyncio.fixture
async def api(db_session: AsyncSession) -> AsyncGenerator[AsyncClient]:
    """An HTTP client sharing the test's rolled-back session."""
    application: FastAPI = create_app()

    async def _session_override() -> AsyncGenerator[AsyncSession]:
        yield db_session

    application.dependency_overrides[get_db_session] = _session_override
    application.dependency_overrides[get_audit_sink] = RecordingAuditSink
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    application.dependency_overrides.clear()


@pytest.fixture
def worker(db_session: AsyncSession) -> NotificationService:
    """The service as the background worker builds it."""
    users = UserRepository(db_session)
    return NotificationService(
        NotificationRepository(db_session),
        users,
        HospitalRepository(db_session),
        db_session,
        RecordingAuditSink(),
    )


async def _deliveries(session: AsyncSession, user_id: uuid.UUID) -> list[NotificationDelivery]:
    """Every delivery of every notification addressed to a user."""
    result = await session.execute(
        select(NotificationDelivery)
        .join(Notification, Notification.id == NotificationDelivery.notification_id)
        .where(Notification.recipient_user_id == user_id)
    )
    return list(result.unique().scalars().all())


async def _user_with_real_address(
    session: AsyncSession, hospital_id: uuid.UUID, permissions: list[str]
) -> User:
    """A user whose address passes the API's email validation.

    The shared helper uses a ``.test`` domain, which is fine for rows but is
    rejected by ``EmailStr`` when it has to travel through a request body.
    """
    user = await insert_user_with_permissions(session, hospital_id, permissions)
    user.email = f"staff-{uuid.uuid4().hex[:12]}@hospital.example"
    await session.flush()
    return user


def _token_in(body: str) -> str:
    """Pull the single-use token out of an emailed link."""
    match = re.search(r"/reset-password\?token=(\S+)", body)
    assert match is not None, "the email carries no reset link"
    return match.group(1)


class TestInvitation:
    """User-management AC-2: "the invited user receives an email"."""

    async def test_an_invite_is_emailed_and_the_emailed_link_activates_the_account(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        worker: NotificationService,
        hospital_id: uuid.UUID,
    ) -> None:
        admin = await insert_user_with_permissions(db_session, hospital_id, ["user.create"])
        email = f"invitee-{uuid.uuid4().hex[:12]}@hospital.example"

        invited = await api.post(
            "/api/v1/users",
            json={"email": email, "first_name": "Nisha", "last_name": "Nair"},
            headers=auth_headers(admin.id, hospital_id),
        )
        assert invited.status_code == 201, invited.text
        user_id = uuid.UUID(invited.json()["data"]["id"])

        # The email is queued in the same transaction as the invite...
        [delivery] = await _deliveries(db_session, user_id)
        assert delivery.status is DeliveryStatus.QUEUED
        assert delivery.hospital_id == hospital_id
        assert delivery.to_address == email
        token = _token_in(delivery.body or "")

        # ...and the in-app copy never contains the token.
        [notification] = (
            (
                await db_session.execute(
                    select(Notification).where(Notification.recipient_user_id == user_id)
                )
            )
            .scalars()
            .all()
        )
        assert notification.kind == "auth.user_invited"
        assert token not in notification.title + notification.body + (notification.link or "")
        assert "Asha Menon invited you" in notification.body

        # The worker sends it.
        outbox = _Outbox()
        report = await worker.deliver_due_emails(outbox)

        assert report.sent == 1
        [message] = outbox.messages
        assert message.to == email
        assert "Hello Nisha," in message.body
        assert token in message.body
        await db_session.refresh(notification)
        [sent] = await _deliveries(db_session, user_id)
        await db_session.refresh(sent)
        assert sent.status is DeliveryStatus.SENT
        assert sent.body is None, "the token must not outlive the email"
        assert notification.sent_email is True

        # And the link in the email really does activate the account.
        reset = await api.post(
            "/api/v1/auth/password/reset", json={"token": token, "new_password": PASSWORD}
        )
        assert reset.status_code == 200, reset.text
        user = await db_session.get(User, user_id)
        assert user is not None
        await db_session.refresh(user)
        assert user.status is UserStatus.ACTIVE

    async def test_a_rejected_invite_leaves_no_notification_behind(
        self, api: AsyncClient, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> None:
        admin = await _user_with_real_address(db_session, hospital_id, ["user.create"])
        before = (await db_session.execute(select(Notification.id))).scalars().all()

        duplicate = await api.post(
            "/api/v1/users",
            json={"email": admin.email, "first_name": "Dup", "last_name": "Licate"},
            headers=auth_headers(admin.id, hospital_id),
        )

        assert duplicate.status_code == 409
        after = (await db_session.execute(select(Notification.id))).scalars().all()
        assert after == before


class TestPasswordReset:
    async def test_a_reset_request_is_emailed_and_the_link_works(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        worker: NotificationService,
        hospital_id: uuid.UUID,
    ) -> None:
        user = await _user_with_real_address(db_session, hospital_id, OWN)
        # Even a user who tried to switch this email off still gets it (AC-4).
        await api.put(
            f"{NOTIFICATIONS}/preferences",
            json={"preferences": {"auth.password_reset_requested": {"email": False}}},
            headers=auth_headers(user.id, hospital_id),
        )

        response = await api.post("/api/v1/auth/password/forgot", json={"email": user.email})
        assert response.status_code == 200, response.text

        outbox = _Outbox()
        await worker.deliver_due_emails(outbox)

        [message] = outbox.messages
        assert message.to == user.email
        token = _token_in(message.body)
        # The in-app notice says a reset was requested, and nothing more.
        centre = await api.get(NOTIFICATIONS, headers=auth_headers(user.id, hospital_id))
        [notice] = centre.json()["data"]
        assert notice["kind"] == "auth.password_reset_requested"
        assert token not in str(notice)

        reset = await api.post(
            "/api/v1/auth/password/reset", json={"token": token, "new_password": PASSWORD}
        )
        assert reset.status_code == 200, reset.text

    async def test_an_unknown_address_sends_nothing(
        self, api: AsyncClient, db_session: AsyncSession, worker: NotificationService
    ) -> None:
        response = await api.post(
            "/api/v1/auth/password/forgot", json={"email": "nobody@hospital.example"}
        )

        assert response.status_code == 200
        outbox = _Outbox()
        await worker.deliver_due_emails(outbox)
        assert outbox.messages == []


class TestDiscountApproval:
    async def test_a_large_discount_lands_in_every_approvers_centre(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        worker: NotificationService,
        hospital_id: uuid.UUID,
        other_hospital_id: uuid.UUID,
    ) -> None:
        hospital = await db_session.get(Hospital, hospital_id)
        assert hospital is not None
        hospital.settings = {"billing": {"discount_approval_threshold_percent": "10"}}
        await db_session.flush()
        approve = [*OWN, "invoice.approve_discount"]
        billing = await insert_user_with_permissions(
            db_session, hospital_id, [*OWN, "invoice.create", "invoice.update", "invoice.read"]
        )
        admin = await insert_user_with_permissions(db_session, hospital_id, approve)
        # Wants this kind by email as well.
        emailed_admin = await insert_user_with_permissions(db_session, hospital_id, approve)
        elsewhere = await insert_user_with_permissions(db_session, other_hospital_id, approve)
        await api.put(
            f"{NOTIFICATIONS}/preferences",
            json={"preferences": {"billing.discount_approval_requested": {"email": True}}},
            headers=auth_headers(emailed_admin.id, hospital_id),
        )
        patient = await insert_patient(db_session, hospital_id)
        billing_headers = auth_headers(billing.id, hospital_id)
        draft = await api.post(
            "/api/v1/invoices",
            json={
                "patient_id": str(patient.id),
                "items": [{"description": "Consultation", "unit_price": "500.00"}],
            },
            headers=billing_headers,
        )
        assert draft.status_code == 201, draft.text

        patched = await api.patch(
            f"/api/v1/invoices/{draft.json()['data']['id']}",
            json={"discount_amount": "200.00", "discount_reason": "Financial hardship"},
            headers=billing_headers,
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["data"]["discount_pending_approval"] is True

        async def centre(user: User, tenant: uuid.UUID) -> list[dict[str, Any]]:
            response = await api.get(NOTIFICATIONS, headers=auth_headers(user.id, tenant))
            return list(response.json()["data"])

        [notice] = await centre(admin, hospital_id)
        assert notice["kind"] == "billing.discount_approval_requested"
        assert notice["link"] == "/billing"
        assert "Ananya Rao" in notice["body"]
        assert "200.00" in notice["body"]
        assert len(await centre(emailed_admin, hospital_id)) == 1
        # Not the person who applied it, and not another hospital's admin.
        assert await centre(billing, hospital_id) == []
        assert await centre(elsewhere, other_hospital_id) == []

        # Only the admin who opted in is emailed.
        outbox = _Outbox()
        await worker.deliver_due_emails(outbox)
        assert [m.to for m in outbox.messages] == [emailed_admin.email]
        assert await _deliveries(db_session, admin.id) == []


class TestEmailQueue:
    async def _queue_one(
        self, api: AsyncClient, db_session: AsyncSession, hospital_id: uuid.UUID
    ) -> NotificationDelivery:
        user = await _user_with_real_address(db_session, hospital_id, OWN)
        await api.post("/api/v1/auth/password/forgot", json={"email": user.email})
        [delivery] = await _deliveries(db_session, user.id)
        return delivery

    async def test_with_email_switched_off_the_delivery_fails_with_a_reason(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        worker: NotificationService,
        hospital_id: uuid.UUID,
    ) -> None:
        delivery = await self._queue_one(api, db_session, hospital_id)

        report = await worker.deliver_due_emails(None)

        assert report.failed == 1
        await db_session.refresh(delivery)
        assert delivery.status is DeliveryStatus.FAILED
        assert "SMTP_HOST" in (delivery.last_error or "")
        assert delivery.body is None

    async def test_a_refused_email_is_retried_later_and_then_sent(
        self,
        api: AsyncClient,
        db_session: AsyncSession,
        worker: NotificationService,
        hospital_id: uuid.UUID,
    ) -> None:
        delivery = await self._queue_one(api, db_session, hospital_id)

        class _Down:
            async def send(self, message: EmailMessage) -> None:
                raise ConnectionRefusedError

        now = datetime.now(UTC)
        first = await worker.deliver_due_emails(_Down(), now=now)
        too_soon = await worker.deliver_due_emails(_Outbox(), now=now + timedelta(seconds=5))
        outbox = _Outbox()
        later = await worker.deliver_due_emails(outbox, now=now + timedelta(minutes=1))

        assert (first.retrying, too_soon.processed, later.sent) == (1, 0, 1)
        await db_session.refresh(delivery)
        assert delivery.status is DeliveryStatus.SENT
        assert delivery.attempts == 2
        assert len(outbox.messages) == 1
