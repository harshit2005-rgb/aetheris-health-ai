"""Hospital settings service — reads and updates the caller's hospital.

Implements the Hospital Admin surface of ``docs/modules/14-hospital-settings.md``
§9. Tenancy is always passed in from the authenticated user; the service never
reads a hospital id from a request body (CLAUDE.md rule 5).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING

from app.core.audit import AuditEvent, AuditSink
from app.core.exceptions import NotFoundError
from app.core.feature_flags import AI_SLOT_RECOMMENDATION, KNOWN_FLAGS, flag_is_on
from app.schemas.hospital import FeatureFlagsResponse, FeatureFlagState

if TYPE_CHECKING:
    from app.database.unit_of_work import UnitOfWork
    from app.models.hospital import Hospital
    from app.models.hospital_working_hours import HospitalWorkingHours
    from app.repositories.hospital_repository import HospitalRepository
    from app.repositories.hospital_working_hours_repository import (
        HospitalWorkingHoursRepository,
    )
    from app.schemas.hospital import SetWorkingHoursRequest, UpdateHospitalSettingsRequest

__all__ = ["HospitalService"]


class HospitalService:
    """Read and update the hospital a user belongs to.

    :param hospitals: Repository bound to the request session.
    :param uow: Transaction coordinator — settings writes commit atomically
        with their audit entry.
    :param audit: Sink every mutation is recorded against.
    :param ai_configured: Whether this server is configured to serve AI
        features. Decides, with the hospital's flag, what the capability read
        reports.
    :param working_hours: The hospital's opening hours. Needed only by the
        working-hours methods.
    """

    def __init__(
        self,
        hospitals: HospitalRepository,
        uow: UnitOfWork,
        audit: AuditSink,
        *,
        ai_configured: bool = False,
        working_hours: HospitalWorkingHoursRepository | None = None,
    ) -> None:
        self._hospitals = hospitals
        self._uow = uow
        self._audit = audit
        self._ai_configured = ai_configured
        self._working_hours = working_hours

    async def get_current(self, hospital_id: uuid.UUID) -> Hospital:
        """Return the caller's hospital.

        :param hospital_id: Tenant to load.
        :returns: The active hospital row.
        :raises NotFoundError: If the hospital does not exist or is inactive.
        """
        hospital = await self._hospitals.get_active_by_id(hospital_id)
        if hospital is None:
            msg = "Hospital not found."
            raise NotFoundError(msg)
        return hospital

    async def get_feature_flags(self, hospital_id: uuid.UUID) -> FeatureFlagsResponse:
        """Report which gated features the caller's hospital can use right now.

        Returns only the well-known flags, one boolean each. A feature is
        available when the hospital's stored flag is exactly ``True`` and the
        server can serve it; the two reasons for "not available" are not told
        apart. Reads one row and calls no provider.

        :param hospital_id: Tenant to report on.
        :returns: The availability of each known flag.
        :raises NotFoundError: If the hospital does not exist or is inactive.
        """
        hospital = await self.get_current(hospital_id)
        # Flags that need something from the server as well as the hospital.
        server_ready = {AI_SLOT_RECOMMENDATION: self._ai_configured}
        return FeatureFlagsResponse(
            flags={
                key: FeatureFlagState(
                    available=flag_is_on(hospital.settings, key) and server_ready.get(key, True)
                )
                for key in KNOWN_FLAGS
            }
        )

    async def update_current(
        self,
        hospital_id: uuid.UUID,
        payload: UpdateHospitalSettingsRequest,
        *,
        actor_id: uuid.UUID,
    ) -> Hospital:
        """Apply an editable-fields update to the caller's hospital.

        Only fields present in the payload change; ``slug``, ``timezone``,
        ``currency`` and ``tax_id`` cannot reach here at all — the request
        schema forbids unknown keys (§9). The diff is captured before the
        write so the audit entry carries before/after values.

        :param hospital_id: Tenant to update.
        :param payload: Validated editable fields.
        :param actor_id: User performing the update.
        :returns: The updated hospital.
        """
        hospital = await self.get_current(hospital_id)

        updates = payload.model_dump(exclude_unset=True)
        if "settings" in updates:
            # Merge, never replace. ``settings`` is shared: the appointment
            # module keeps its no-show grace period and feature flags there,
            # billing its tax rate. A PATCH that sent one key used to wipe
            # every other one. A key sent as null is removed.
            merged = dict(hospital.settings or {})
            for key, value in updates["settings"].items():
                if value is None:
                    merged.pop(key, None)
                else:
                    merged[key] = value
            updates["settings"] = merged

        changes: dict[str, dict[str, object]] = {}
        for field, new_value in updates.items():
            old_value = getattr(hospital, field)
            if old_value != new_value:
                changes[field] = {"before": old_value, "after": new_value}

        if not changes:
            return hospital

        hospital = await self._hospitals.update(hospital, **updates)

        await self._audit.record(
            AuditEvent(
                action="settings.hospital_updated",
                hospital_id=hospital.id,
                target_type="hospital",
                target_id=hospital.id,
                actor_id=actor_id,
                changes=changes,
            )
        )
        await self._uow.commit()
        return hospital

    # ── Working hours (§8, §9) ─────────────────────────────────────────────────

    def _hours(self) -> HospitalWorkingHoursRepository:
        if self._working_hours is None:  # pragma: no cover — wiring error, not a request error
            msg = "HospitalService was built without a working-hours repository."
            raise RuntimeError(msg)
        return self._working_hours

    async def get_working_hours(self, hospital_id: uuid.UUID) -> list[HospitalWorkingHours]:
        """The caller's hospital's opening hours, Monday first.

        :param hospital_id: Tenant to read.
        :returns: One row per day that has an entry.
        :raises NotFoundError: If the hospital does not exist or is inactive.
        """
        await self.get_current(hospital_id)
        return await self._hours().list_for_hospital(hospital_id)

    async def set_working_hours(
        self,
        hospital_id: uuid.UUID,
        payload: SetWorkingHoursRequest,
        *,
        actor_id: uuid.UUID,
    ) -> list[HospitalWorkingHours]:
        """Replace the caller's hospital's week of opening hours (§9).

        Atomic with its audit entry, which carries the week before and after.

        :param hospital_id: Tenant to update.
        :param payload: The whole week, validated.
        :param actor_id: User making the change.
        :returns: The stored week, Monday first.
        :raises NotFoundError: If the hospital does not exist or is inactive.
        """
        await self.get_current(hospital_id)
        repository = self._hours()
        before = [_describe_day(row) for row in await repository.list_for_hospital(hospital_id)]
        rows = await repository.replace_for_hospital(
            hospital_id,
            [day.model_dump() for day in sorted(payload.days, key=lambda day: day.day_of_week)],
            actor_id=actor_id,
        )
        after = [_describe_day(row) for row in rows]
        if before != after:
            await self._audit.record(
                AuditEvent(
                    action="settings.working_hours_updated",
                    hospital_id=hospital_id,
                    target_type="hospital",
                    target_id=hospital_id,
                    actor_id=actor_id,
                    changes={"working_hours": {"before": before, "after": after}},
                )
            )
        await self._uow.commit()
        return rows


def _describe_day(row: HospitalWorkingHours) -> dict[str, object]:
    """One day as plain JSON for the audit trail."""
    return {
        "day_of_week": row.day_of_week,
        "is_24h": row.is_24h,
        "open_time": row.open_time.isoformat() if row.open_time else None,
        "close_time": row.close_time.isoformat() if row.close_time else None,
    }
