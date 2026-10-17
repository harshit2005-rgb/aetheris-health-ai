"""Consultation (EMR) business logic (``docs/modules/16-consultation.md``).

Rules enforced here (numbers refer to §4):

1. One note per appointment — the unique index is the backstop; a clash is 409.
2. A note is started only for a visit that is checked in, in progress or completed.
3. Only the appointment's doctor writes clinical sections, finalizes or adds
   addenda. ``consultation.write`` is necessary, not sufficient.
4. Vitals can be recorded by anyone with ``consultation.vitals.record`` while
   the note is a draft.
5. Finalizing needs a chief complaint and at least one diagnosis.
6. A finalized note is never edited; addenda are added instead.
7. Patient, doctor and appointment come from the appointment, never the request.
8. Every change writes an audit entry.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import IntegrityError

from app.core.audit import AuditEvent
from app.core.exceptions import (
    BusinessRuleError,
    ConflictError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)
from app.core.logging import get_logger
from app.models.appointment import AppointmentStatus
from app.models.consultation import Consultation, ConsultationStatus
from app.schemas.common import Page, PaginationParams
from app.schemas.consultation import (
    ConsultationResponse,
    ConsultationSummary,
)
from app.services.pharmacy_common import hospital_today

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.audit import AuditSink
    from app.models.appointment import Appointment
    from app.repositories.appointment_repository import AppointmentRepository
    from app.repositories.consultation_repository import ConsultationRepository
    from app.repositories.hospital_repository import HospitalRepository
    from app.repositories.lab_order_repository import LabOrderRepository
    from app.repositories.prescription_repository import PrescriptionRepository
    from app.schemas.consultation import (
        AddAddendumRequest,
        CreateConsultationRequest,
        UpdateConsultationRequest,
        Vitals,
    )

logger = get_logger(__name__)

__all__ = [
    "ConsultationNotFoundError",
    "ConsultationService",
]

#: Visits a note can be started for (rule 2).
_DOCUMENTABLE: frozenset[AppointmentStatus] = frozenset(
    {AppointmentStatus.CHECKED_IN, AppointmentStatus.IN_PROGRESS, AppointmentStatus.COMPLETED}
)
#: Fields of a draft the doctor may change (rule 3).
_SECTIONS = ("chief_complaint", "history", "examination", "diagnoses", "plan", "follow_up_date")


class ConsultationNotFoundError(NotFoundError):
    """Raised when a consultation is absent from this hospital."""

    def __init__(self, consultation_id: uuid.UUID | None = None) -> None:
        super().__init__(
            message="Consultation not found.",
            detail={"consultation_id": str(consultation_id)} if consultation_id else None,
        )


class _AppointmentNotFoundError(NotFoundError):
    def __init__(self, appointment_id: uuid.UUID) -> None:
        super().__init__(
            message="Appointment not found.", detail={"appointment_id": str(appointment_id)}
        )


def _not_own() -> PermissionDeniedError:
    return PermissionDeniedError(
        message="Only the doctor seeing this patient can write their consultation note."
    )


def _finalized() -> BusinessRuleError:
    return BusinessRuleError(
        message="This consultation is finalized and cannot be changed. Add an addendum instead.",
        detail={"status": ConsultationStatus.FINALIZED.value},
    )


class ConsultationService:
    """Writing, finalizing and reading consultation notes.

    :param consultations: Consultation data access.
    :param appointments: Appointment lookups, for the visit a note documents.
    :param prescriptions: Prescription lookups, for the visit's prescriptions.
    :param lab_orders: Lab order lookups, for the visit's tests.
    :param hospitals: Hospital lookups, for the hospital's calendar date.
    :param session: Request-scoped session; the service owns the transaction.
    :param audit: Where audit events are recorded.
    """

    def __init__(
        self,
        consultations: ConsultationRepository,
        appointments: AppointmentRepository,
        prescriptions: PrescriptionRepository,
        lab_orders: LabOrderRepository,
        hospitals: HospitalRepository,
        session: AsyncSession,
        audit: AuditSink,
    ) -> None:
        self._consultations = consultations
        self._appointments = appointments
        self._prescriptions = prescriptions
        self._lab_orders = lab_orders
        self._hospitals = hospitals
        self._session = session
        self._audit = audit

    # ── Helpers ──────────────────────────────────────────────────────────────

    async def _appointment(self, hospital_id: uuid.UUID, appointment_id: uuid.UUID) -> Appointment:
        appointment = await self._appointments.get_appointment_by_id(hospital_id, appointment_id)
        if appointment is None:
            raise _AppointmentNotFoundError(appointment_id)
        return appointment

    @staticmethod
    def _require_documentable(appointment: Appointment) -> None:
        if appointment.status not in _DOCUMENTABLE:
            hint = (
                "Check the patient in first."
                if appointment.status is AppointmentStatus.BOOKED
                else "This visit did not take place."
            )
            raise BusinessRuleError(
                message=(
                    "A consultation can only be written for a visit that is checked in, "
                    f"in progress or completed. {hint}"
                ),
                detail={"appointment_status": appointment.status.value},
            )

    async def _get(
        self, hospital_id: uuid.UUID, consultation_id: uuid.UUID, *, for_update: bool = False
    ) -> Consultation:
        consultation = await self._consultations.get_for_hospital(
            hospital_id, consultation_id, for_update=for_update
        )
        if consultation is None:
            raise ConsultationNotFoundError(consultation_id)
        return consultation

    @staticmethod
    def _is_own(consultation: Consultation, actor_id: uuid.UUID | None) -> bool:
        return actor_id is not None and consultation.doctor.user_id == actor_id

    async def _validate_follow_up(self, hospital_id: uuid.UUID, follow_up: date | None) -> None:
        if follow_up is None:
            return
        today = await hospital_today(self._hospitals, hospital_id)
        if follow_up < today:
            raise ValidationError(
                message="Validation failed.",
                detail={
                    "errors": [
                        {
                            "field": "follow_up_date",
                            "message": "The follow-up date cannot be in the past.",
                        }
                    ]
                },
            )

    async def _respond(
        self, consultation: Consultation, actor_id: uuid.UUID | None
    ) -> ConsultationResponse:
        prescriptions = await self._prescriptions.list_prescriptions(
            consultation.hospital_id, appointment_id=consultation.appointment_id, limit=100
        )
        lab_orders = await self._lab_orders.list_orders(
            consultation.hospital_id, appointment_id=consultation.appointment_id, limit=100
        )
        return ConsultationResponse.build(
            consultation,
            is_own=self._is_own(consultation, actor_id),
            prescriptions=prescriptions,
            lab_orders=lab_orders,
        )

    @staticmethod
    def _section_values(payload: Any) -> dict[str, Any]:
        """The clinical sections the request actually sent, ready to store."""
        values: dict[str, Any] = {}
        for name in _SECTIONS:
            if name not in payload.model_fields_set:
                continue
            value = getattr(payload, name)
            if name == "diagnoses":
                value = [d.model_dump() for d in value] if value is not None else []
            elif isinstance(value, str) and not value:
                value = None
            values[name] = value
        return values

    async def _audit_event(
        self,
        action: str,
        consultation: Consultation,
        actor_id: uuid.UUID | None,
        context: dict[str, Any] | None = None,
    ) -> None:
        await self._audit.record(
            AuditEvent(
                action=action,
                hospital_id=consultation.hospital_id,
                target_type="consultation",
                target_id=consultation.id,
                actor_id=actor_id,
                context={"appointment_id": str(consultation.appointment_id), **(context or {})},
            )
        )

    # ── Commands ─────────────────────────────────────────────────────────────

    async def create(
        self,
        hospital_id: uuid.UUID,
        payload: CreateConsultationRequest,
        *,
        actor_id: uuid.UUID,
    ) -> ConsultationResponse:
        """Start the note for a visit (FR-1).

        :raises PermissionDeniedError: If the caller is not the visit's doctor (rule 3).
        :raises BusinessRuleError: If the visit is not under way (rule 2).
        :raises ConflictError: If the visit already has a note (rule 1).
        """
        appointment = await self._appointment(hospital_id, payload.appointment_id)
        if appointment.doctor.user_id != actor_id:
            raise _not_own()
        self._require_documentable(appointment)
        await self._validate_follow_up(hospital_id, payload.follow_up_date)

        fields = self._section_values(payload)
        if payload.vitals is not None:
            fields.update(
                vitals=payload.vitals.to_json(),
                vitals_recorded_at=datetime.now(UTC),
                vitals_recorded_by=actor_id,
            )
        consultation = await self._insert(appointment, actor_id, fields)
        await self._audit_event(
            "consultation.created", consultation, actor_id, {"sections": sorted(fields)}
        )
        await self._session.commit()
        logger.info(
            "consultation.created",
            hospital_id=str(hospital_id),
            consultation_id=str(consultation.id),
        )
        return await self._respond(consultation, actor_id)

    async def _insert(
        self, appointment: Appointment, actor_id: uuid.UUID, fields: dict[str, Any]
    ) -> Consultation:
        # Read everything needed before any rollback expires the instance.
        hospital_id, appointment_id = appointment.hospital_id, appointment.id
        conflict = ConflictError(
            message="This visit already has a consultation note.",
            detail={"appointment_id": str(appointment_id)},
        )
        if await self._consultations.get_by_appointment(hospital_id, appointment_id) is not None:
            raise conflict
        try:
            return await self._consultations.create_consultation(
                hospital_id=hospital_id,
                appointment_id=appointment_id,
                patient_id=appointment.patient_id,
                doctor_id=appointment.doctor_id,
                created_by=actor_id,
                **fields,
            )
        except IntegrityError as exc:
            # A second note raced this one past the check above (rule 1).
            await self._session.rollback()
            raise conflict from exc

    async def update(
        self,
        hospital_id: uuid.UUID,
        consultation_id: uuid.UUID,
        payload: UpdateConsultationRequest,
        *,
        actor_id: uuid.UUID,
    ) -> ConsultationResponse:
        """Change clinical sections of a draft (FR-2).

        :raises PermissionDeniedError: If the caller is not the note's doctor.
        :raises BusinessRuleError: If the note is finalized (rule 6).
        """
        consultation = await self._get(hospital_id, consultation_id, for_update=True)
        if not self._is_own(consultation, actor_id):
            raise _not_own()
        if consultation.status is ConsultationStatus.FINALIZED:
            raise _finalized()
        await self._validate_follow_up(hospital_id, payload.follow_up_date)
        fields = self._section_values(payload)
        consultation = await self._consultations.update_consultation(
            consultation, updated_by=actor_id, **fields
        )
        await self._audit_event(
            "consultation.updated", consultation, actor_id, {"sections": sorted(fields)}
        )
        await self._session.commit()
        return await self._respond(consultation, actor_id)

    async def record_vitals(
        self,
        hospital_id: uuid.UUID,
        consultation_id: uuid.UUID,
        vitals: Vitals,
        *,
        actor_id: uuid.UUID,
    ) -> ConsultationResponse:
        """Record (replace) the vitals on a draft (FR-3, rule 4)."""
        consultation = await self._get(hospital_id, consultation_id, for_update=True)
        return await self._store_vitals(consultation, vitals, actor_id)

    async def record_vitals_for_appointment(
        self,
        hospital_id: uuid.UUID,
        appointment_id: uuid.UUID,
        vitals: Vitals,
        *,
        actor_id: uuid.UUID,
    ) -> ConsultationResponse:
        """Record vitals for a visit, starting its draft note if needed (the nurse's entry)."""
        consultation = await self._consultations.get_by_appointment(hospital_id, appointment_id)
        if consultation is None:
            appointment = await self._appointment(hospital_id, appointment_id)
            self._require_documentable(appointment)
            consultation = await self._insert(appointment, actor_id, {})
            await self._audit_event(
                "consultation.created", consultation, actor_id, {"sections": []}
            )
        else:
            consultation = await self._get(hospital_id, consultation.id, for_update=True)
        return await self._store_vitals(consultation, vitals, actor_id)

    async def _store_vitals(
        self, consultation: Consultation, vitals: Vitals, actor_id: uuid.UUID
    ) -> ConsultationResponse:
        if consultation.status is ConsultationStatus.FINALIZED:
            raise _finalized()
        consultation = await self._consultations.update_consultation(
            consultation,
            updated_by=actor_id,
            vitals=vitals.to_json(),
            vitals_recorded_at=datetime.now(UTC),
            vitals_recorded_by=actor_id,
        )
        await self._audit_event(
            "consultation.vitals_recorded",
            consultation,
            actor_id,
            {"fields": sorted(vitals.to_json())},
        )
        await self._session.commit()
        return await self._respond(consultation, actor_id)

    async def finalize(
        self, hospital_id: uuid.UUID, consultation_id: uuid.UUID, *, actor_id: uuid.UUID
    ) -> ConsultationResponse:
        """Lock the note (FR-4, rule 5).

        :raises ValidationError: Without a chief complaint or a diagnosis.
        """
        consultation = await self._get(hospital_id, consultation_id, for_update=True)
        if not self._is_own(consultation, actor_id):
            raise _not_own()
        if consultation.status is ConsultationStatus.FINALIZED:
            raise _finalized()
        missing = []
        if not (consultation.chief_complaint or "").strip():
            missing.append(
                {"field": "chief_complaint", "message": "Add the chief complaint first."}
            )
        if not consultation.diagnoses:
            missing.append({"field": "diagnoses", "message": "Add at least one diagnosis first."})
        if missing:
            raise ValidationError(
                message="The note is not complete enough to finalize.",
                detail={"errors": missing},
            )
        now = datetime.now(UTC)
        consultation = await self._consultations.update_consultation(
            consultation,
            updated_by=actor_id,
            status=ConsultationStatus.FINALIZED,
            finalized_at=now,
            finalized_by=actor_id,
        )
        await self._audit_event(
            "consultation.finalized",
            consultation,
            actor_id,
            {"diagnoses": len(consultation.diagnoses)},
        )
        await self._session.commit()
        logger.info(
            "consultation.finalized",
            hospital_id=str(hospital_id),
            consultation_id=str(consultation.id),
        )
        return await self._respond(consultation, actor_id)

    async def add_addendum(
        self,
        hospital_id: uuid.UUID,
        consultation_id: uuid.UUID,
        payload: AddAddendumRequest,
        *,
        actor_id: uuid.UUID,
    ) -> ConsultationResponse:
        """Add to a finalized note (FR-5, rule 6).

        :raises BusinessRuleError: If the note is still a draft — edit it instead.
        """
        consultation = await self._get(hospital_id, consultation_id, for_update=True)
        if not self._is_own(consultation, actor_id):
            raise _not_own()
        if consultation.status is not ConsultationStatus.FINALIZED:
            raise BusinessRuleError(
                message="This consultation is still a draft: edit it instead of adding an addendum.",
                detail={"status": consultation.status.value},
            )
        consultation = await self._consultations.add_addendum(
            consultation, text=payload.text, added_by=actor_id, added_at=datetime.now(UTC)
        )
        await self._audit_event("consultation.addendum_added", consultation, actor_id)
        await self._session.commit()
        return await self._respond(consultation, actor_id)

    # ── Queries ──────────────────────────────────────────────────────────────

    async def get(
        self, hospital_id: uuid.UUID, consultation_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> ConsultationResponse:
        """One note in full, with the visit's prescriptions and lab orders (FR-6)."""
        return await self._respond(await self._get(hospital_id, consultation_id), actor_id)

    async def get_for_appointment(
        self, hospital_id: uuid.UUID, appointment_id: uuid.UUID, *, actor_id: uuid.UUID | None
    ) -> ConsultationResponse:
        """The note of one visit.

        :raises ConsultationNotFoundError: If the visit has no note yet.
        """
        consultation = await self._consultations.get_by_appointment(hospital_id, appointment_id)
        if consultation is None:
            raise ConsultationNotFoundError()
        return await self._respond(consultation, actor_id)

    async def list_consultations(
        self,
        hospital_id: uuid.UUID,
        *,
        pagination: PaginationParams | None = None,
        patient_id: uuid.UUID | None = None,
        doctor_id: uuid.UUID | None = None,
        appointment_id: uuid.UUID | None = None,
        status: ConsultationStatus | None = None,
    ) -> Page[ConsultationSummary]:
        """A page of notes, newest first (FR-7)."""
        page_params = pagination or PaginationParams()
        rows, total = await self._consultations.list_page(
            hospital_id,
            offset=page_params.offset,
            limit=page_params.page_size,
            patient_id=patient_id,
            doctor_id=doctor_id,
            appointment_id=appointment_id,
            status=status,
        )
        return Page[ConsultationSummary](
            items=[ConsultationSummary.from_model(row) for row in rows],
            page=page_params.page,
            page_size=page_params.page_size,
            total_records=total,
        )
