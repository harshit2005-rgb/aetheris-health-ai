"""Medical Record Number generation.

Implements ``MRNService.next(hospital_id)`` from
``docs/modules/03-patient-management.md`` §5.1: reserve the next value from the
hospital's counter, then render it through the hospital's format template.

Split out from :class:`~app.services.patient_service.PatientService` because
the module spec names it as its own service, and because doctors, appointments,
and future importers all need MRNs without needing patient business rules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.exceptions import ConfigurationError
from app.core.logging import get_logger
from app.utils.datetime import utc_today
from app.utils.mrn import InvalidMrnTemplateError, format_mrn

if TYPE_CHECKING:
    import uuid
    from datetime import date

    from app.repositories.mrn_sequence_repository import MrnSequenceRepository

logger = get_logger(__name__)


class MRNService:
    """Generates Medical Record Numbers that are unique per hospital.

    :param sequences: Repository for the ``mrn_sequences`` counter table.
    """

    def __init__(self, sequences: MrnSequenceRepository) -> None:
        self._sequences = sequences

    async def next(self, hospital_id: uuid.UUID, *, issued_on: date | None = None) -> str:
        """Reserve and render the next MRN for a hospital.

        Must be called inside the caller's transaction: the counter row is
        locked by
        :meth:`~app.repositories.mrn_sequence_repository.MrnSequenceRepository.advance`
        and stays locked until that transaction ends. Calling this outside a
        transaction reserves a value that nothing holds, which will show up
        later as a gap in the MRN series.

        :param hospital_id: The hospital to generate an MRN for.
        :param issued_on: Date the MRN is considered issued on, used for the
            ``{year}`` placeholder. Defaults to today in UTC.
        :returns: The rendered MRN, e.g. ``MRN-2026-00042``.
        :raises ConfigurationError: If the hospital's stored template is
            invalid or renders past the 30-character column limit. This is a
            misconfiguration, not user input — it must not be reported to the
            caller as a validation failure.
        """
        sequence_value, template = await self._sequences.advance(hospital_id)
        year = (issued_on or utc_today()).year

        try:
            mrn = format_mrn(template, year=year, sequence=sequence_value)
        except InvalidMrnTemplateError as exc:
            logger.error(
                "mrn.template_invalid",
                hospital_id=str(hospital_id),
                sequence_value=sequence_value,
                reason=str(exc),
            )
            msg = "The hospital's MRN format is misconfigured."
            raise ConfigurationError(
                msg,
                detail={"hospital_id": str(hospital_id)},
            ) from exc

        logger.debug(
            "mrn.generated",
            hospital_id=str(hospital_id),
            sequence_value=sequence_value,
        )
        return mrn
