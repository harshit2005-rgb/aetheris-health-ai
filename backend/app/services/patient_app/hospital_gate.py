"""Which hospitals the Patient App may be used with.

A hospital is open to patients only when it is active **and** has the Patient
App switched on (``feature.patient_app.enabled``). Every other state — no such
hospital, an inactive one, the flag off or holding an unexpected value — is
one answer, ``None``, and callers turn it into the same "not found" a patient
gets for a record that does not match. Nothing here says which it was.
"""

from __future__ import annotations

import re
import uuid
from typing import TYPE_CHECKING, Final

from app.core.feature_flags import PATIENT_APP_ENABLED, flag_is_on

if TYPE_CHECKING:
    from app.repositories.hospital_repository import HospitalRepository, HospitalSummary

__all__ = ["PatientHospitalGate"]

#: A hospital id exactly as ``str(uuid)`` writes it. Other spellings a UUID
#: parser would accept are not: one hospital has one reference.
_UUID_TEXT: Final = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
#: A hospital slug: the code a hospital gives its patients.
_SLUG: Final = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


class PatientHospitalGate:
    """Resolves a hospital for a patient request, or refuses to.

    :param hospitals: Hospital data access.
    """

    def __init__(self, hospitals: HospitalRepository) -> None:
        self._hospitals = hospitals

    async def resolve(self, hospital_ref: str) -> HospitalSummary | None:
        """Find the enabled hospital a patient named by its id or its code.

        :param hospital_ref: The hospital UUID, or its slug.
        :returns: The hospital, or ``None`` if it cannot be used.
        """
        reference = hospital_ref.strip().lower()
        if _UUID_TEXT.fullmatch(reference):
            hospital = await self._hospitals.get_active_summary(id=uuid.UUID(reference))
        elif _SLUG.fullmatch(reference):
            hospital = await self._hospitals.get_active_summary(slug=reference)
        else:
            return None
        return self._if_enabled(hospital)

    async def get_enabled(self, hospital_id: uuid.UUID) -> HospitalSummary | None:
        """Find an enabled hospital by an id the server already holds.

        :param hospital_id: The hospital UUID.
        :returns: The hospital, or ``None`` if it cannot be used.
        """
        return self._if_enabled(await self._hospitals.get_active_summary(id=hospital_id))

    @staticmethod
    def _if_enabled(hospital: HospitalSummary | None) -> HospitalSummary | None:
        """Keep a hospital only if it has the Patient App switched on."""
        if hospital is None or not flag_is_on(hospital.settings, PATIENT_APP_ENABLED):
            return None
        return hospital
