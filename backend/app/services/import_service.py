"""Spreadsheet import (``docs/modules/17-data-import-export.md``).

Each row is turned into the same request DTO its own screen would send, then
created through that module's own service (rule 3): MRNs, uniqueness checks
and audit entries behave exactly as they do by hand. A row matching an existing
record is skipped and reported, never overwritten (rule 4). A dry run saves
nothing (rule 5).
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError

from app.core.audit import AuditEvent
from app.core.exceptions import AtherisError, ConflictError, NotFoundError
from app.core.logging import get_logger
from app.schemas.billing import CreateServiceRequest
from app.schemas.data_import import ImportProblem, ImportReport, ImportSkip
from app.schemas.lab import CreateLabTestRequest
from app.schemas.patient import CreatePatientRequest
from app.schemas.pharmacy import CreateMedicineRequest
from app.utils.spreadsheet import (
    CellError,
    SheetData,
    parse_bool,
    parse_date,
    parse_decimal,
    parse_int,
    parse_phone,
    workbook_bytes,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.core.audit import AuditSink
    from app.repositories.lab_test_repository import LabTestRepository
    from app.repositories.medicine_repository import MedicineRepository
    from app.repositories.patient_repository import PatientRepository
    from app.repositories.service_catalog_repository import ServiceCatalogRepository
    from app.services.lab_catalog_service import LabCatalogService
    from app.services.patient_service import PatientService
    from app.services.pharmacy_catalog_service import PharmacyCatalogService
    from app.services.service_catalog_service import ServiceCatalogService

logger = get_logger(__name__)

__all__ = ["IMPORT_KINDS", "ImportService", "UnknownImportKindError"]


class UnknownImportKindError(NotFoundError):
    """Raised for an import kind that does not exist."""

    def __init__(self, kind: str) -> None:
        super().__init__(
            message=f"Nothing can be imported as '{kind}'.",
            detail={"kinds": sorted(IMPORT_KINDS)},
        )


def _text(value: object) -> str:
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


_GENDERS: Final = {
    "male": "male",
    "m": "male",
    "female": "female",
    "f": "female",
    "other": "other",
    "o": "other",
    "unspecified": "unspecified",
    "unknown": "unspecified",
}


def _gender(value: object) -> str:
    gender = _GENDERS.get(_text(value).lower())
    if gender is None:
        msg = "Use male, female or other."
        raise CellError(msg)
    return gender


def _upper(value: object) -> str:
    return _text(value).upper()


@dataclass(frozen=True, slots=True)
class Column:
    """One column of an import template."""

    key: str
    label: str
    required: bool = False
    parse: Callable[[object], Any] = _text
    hint: str = ""
    example: str = ""


@dataclass(frozen=True, slots=True)
class ImportKind:
    """What can be imported: its columns and how a row becomes a request."""

    title: str
    columns: tuple[Column, ...]
    build: Callable[[dict[str, Any]], BaseModel]
    #: Request field name → template column key, for mapping validation errors.
    field_columns: dict[str, str] = field(default_factory=dict)
    #: Rules across columns, as ``(column label, message)`` problems.
    check: Callable[[dict[str, Any]], list[tuple[str, str]]] | None = None


def _check_patient(values: dict[str, Any]) -> list[tuple[str, str]]:
    """An address needs a street line and a city, as on the registration screen."""
    if not any(values.get(k) for k in ("address_line_1", "city", "state", "pin_code")):
        return []
    message = "An address needs Address line 1 and City; fill both or leave the address empty."
    return [
        (label, message)
        for key, label in (("address_line_1", "Address line 1"), ("city", "City"))
        if not values.get(key)
    ]


def _patient(values: dict[str, Any]) -> BaseModel:
    address = None
    if any(values.get(k) for k in ("address_line_1", "city", "state", "pin_code")):
        address = {
            "line1": values.get("address_line_1") or "",
            "city": values.get("city") or "",
            "state": values.get("state"),
            "postal_code": values.get("pin_code"),
            "country": "IN",
        }
    notes = values.get("notes")
    previous = values.get("previous_record_no")
    if previous:
        notes = f"Previous record no.: {previous}" + (f"\n{notes}" if notes else "")
    return CreatePatientRequest.model_validate(
        {
            "first_name": values.get("first_name"),
            "last_name": values.get("last_name"),
            "date_of_birth": values.get("date_of_birth"),
            "gender": values.get("gender"),
            "phone": values.get("phone"),
            "email": values.get("email"),
            "blood_group": values.get("blood_group"),
            "address": address,
            "notes": notes,
        }
    )


def _service(values: dict[str, Any]) -> BaseModel:
    body = {k: values[k] for k in ("code", "name", "category", "price") if k in values}
    if "taxable" in values:
        body["taxable"] = values["taxable"]
    return CreateServiceRequest.model_validate(body)


def _medicine(values: dict[str, Any]) -> BaseModel:
    body = {
        "sku": values.get("sku"),
        "name": values.get("name"),
        "generic_name": values.get("generic_name"),
        "strength": values.get("strength"),
        "form": values.get("form"),
        "unit_price": values.get("price"),
    }
    if "prescription_required" in values:
        body["requires_prescription"] = values["prescription_required"]
    return CreateMedicineRequest.model_validate(body)


def _lab_test(values: dict[str, Any]) -> BaseModel:
    ranges = []
    if values.get("reference_low") is not None or values.get("reference_high") is not None:
        ranges.append(
            {"sex": "any", "low": values.get("reference_low"), "high": values.get("reference_high")}
        )
    body: dict[str, Any] = {
        "code": values.get("code"),
        "name": values.get("name"),
        "category": values.get("category"),
        "unit": values.get("unit"),
        "reference_ranges": ranges,
        "turnaround_hours": values.get("turnaround_hours"),
    }
    if values.get("result_type"):
        body["result_type"] = str(values["result_type"]).lower()
    if values.get("price") is not None:
        body["price"] = values["price"]
    return CreateLabTestRequest.model_validate(body)


IMPORT_KINDS: Final[dict[str, ImportKind]] = {
    "patients": ImportKind(
        title="Patients",
        columns=(
            Column("first_name", "First name", required=True, example="Ananya"),
            Column("last_name", "Last name", required=True, example="Rao"),
            Column(
                "date_of_birth",
                "Date of birth",
                required=True,
                parse=parse_date,
                hint="YYYY-MM-DD or DD/MM/YYYY",
                example="1990-01-31",
            ),
            Column(
                "gender",
                "Gender",
                required=True,
                parse=_gender,
                hint="male / female / other",
                example="female",
            ),
            Column(
                "phone", "Phone", parse=parse_phone, hint="10-digit mobile", example="9812345678"
            ),
            Column("email", "Email", example="ananya@example.com"),
            Column("blood_group", "Blood group", parse=_upper, hint="A+, O-, ...", example="B+"),
            Column("address_line_1", "Address line 1", example="12 MG Road"),
            Column("city", "City", example="Hyderabad"),
            Column("state", "State", example="Telangana"),
            Column("pin_code", "PIN code", example="500072"),
            Column(
                "previous_record_no",
                "Previous record no.",
                hint="Your old system's number; kept in the notes",
                example="OLD-1042",
            ),
            Column("notes", "Notes"),
        ),
        build=_patient,
        field_columns={"address": "address_line_1", "postal_code": "pin_code"},
        check=_check_patient,
    ),
    "services": ImportKind(
        title="Services",
        columns=(
            Column("code", "Code", required=True, parse=_upper, example="CONS-GEN"),
            Column("name", "Name", required=True, example="General consultation"),
            Column("category", "Category", example="Consultation"),
            Column("price", "Price", required=True, parse=parse_decimal, example="500"),
            Column("taxable", "Taxable", parse=parse_bool, hint="yes / no", example="no"),
        ),
        build=_service,
    ),
    "medicines": ImportKind(
        title="Medicines",
        columns=(
            Column("sku", "SKU", required=True, parse=_upper, example="PARA-500"),
            Column("name", "Name", required=True, example="Paracetamol 500 mg"),
            Column("generic_name", "Generic name", example="Paracetamol"),
            Column("strength", "Strength", example="500 mg"),
            Column("form", "Form", example="tablet"),
            Column("price", "Price", required=True, parse=parse_decimal, example="2.50"),
            Column(
                "prescription_required",
                "Prescription required",
                parse=parse_bool,
                hint="yes / no",
                example="no",
            ),
        ),
        build=_medicine,
        field_columns={"unit_price": "price", "requires_prescription": "prescription_required"},
    ),
    "lab-tests": ImportKind(
        title="Lab tests",
        columns=(
            Column("code", "Code", required=True, parse=_upper, example="HB"),
            Column("name", "Name", required=True, example="Haemoglobin"),
            Column("category", "Category", example="Haematology"),
            Column("unit", "Unit", example="g/dL"),
            Column("result_type", "Result type", hint="numeric / text", example="numeric"),
            Column("reference_low", "Reference low", parse=parse_decimal, example="12"),
            Column("reference_high", "Reference high", parse=parse_decimal, example="15.5"),
            Column("turnaround_hours", "Turnaround hours", parse=parse_int, example="4"),
            Column("price", "Price", parse=parse_decimal, example="250"),
        ),
        build=_lab_test,
        field_columns={"reference_ranges": "reference_low"},
    ),
}


def _kind(kind: str) -> ImportKind:
    found = IMPORT_KINDS.get(kind)
    if found is None:
        raise UnknownImportKindError(kind)
    return found


class ImportService:
    """Templates and imports for patients and the hospital's catalogs.

    :param patients: Patient registration (MRNs, validation, audit).
    :param services: Billing service catalog.
    :param medicines: Pharmacy medicine catalog.
    :param lab_tests: Laboratory test catalog.
    :param patient_lookup: Finds an already-registered patient.
    :param service_lookup: Finds a service by code.
    :param medicine_lookup: Finds a medicine by SKU.
    :param lab_test_lookup: Finds a lab test by code.
    :param session: Request-scoped session, for the import's own audit entry.
    :param audit: Where audit events are recorded.
    """

    def __init__(
        self,
        *,
        patients: PatientService,
        services: ServiceCatalogService,
        medicines: PharmacyCatalogService,
        lab_tests: LabCatalogService,
        patient_lookup: PatientRepository,
        service_lookup: ServiceCatalogRepository,
        medicine_lookup: MedicineRepository,
        lab_test_lookup: LabTestRepository,
        session: AsyncSession,
        audit: AuditSink,
    ) -> None:
        self._patients = patients
        self._services = services
        self._medicines = medicines
        self._lab_tests = lab_tests
        self._patient_lookup = patient_lookup
        self._service_lookup = service_lookup
        self._medicine_lookup = medicine_lookup
        self._lab_test_lookup = lab_test_lookup
        self._session = session
        self._audit = audit

    # ── Templates ────────────────────────────────────────────────────────────

    @staticmethod
    def template(kind: str) -> tuple[str, bytes]:
        """A blank ``.xlsx`` template with an instructions sheet (FR-1).

        :returns: ``(file name, bytes)``.
        :raises UnknownImportKindError: For an unknown kind.
        """
        spec = _kind(kind)
        headers = [
            f"{c.label} ({c.hint})" if c.hint and c.parse is parse_date else c.label
            for c in spec.columns
        ]
        instructions = [
            (
                c.label,
                "Required" if c.required else "Optional",
                c.hint,
                c.example,
            )
            for c in spec.columns
        ]
        content = workbook_bytes(
            [
                (spec.title, headers, []),
                ("Instructions", ["Column", "Required?", "Format", "Example"], instructions),
            ]
        )
        return f"atheris-{kind}-template.xlsx", content

    # ── Import ───────────────────────────────────────────────────────────────

    def _row_values(
        self, spec: ImportKind, number: int, raw: dict[str, Any], problems: list[ImportProblem]
    ) -> dict[str, Any] | None:
        values: dict[str, Any] = {}
        ok = True
        for column in spec.columns:
            cell = raw.get(column.key)
            if cell is None:
                if column.required:
                    problems.append(
                        ImportProblem(row=number, column=column.label, message="Required.")
                    )
                    ok = False
                continue
            try:
                values[column.key] = column.parse(cell)
            except CellError as exc:
                problems.append(ImportProblem(row=number, column=column.label, message=str(exc)))
                ok = False
        if ok and spec.check is not None:
            for label, message in spec.check(values):
                problems.append(ImportProblem(row=number, column=label, message=message))
                ok = False
        return values if ok else None

    @staticmethod
    def _label_for(spec: ImportKind, loc: tuple[Any, ...]) -> str:
        names = [str(part) for part in loc if isinstance(part, str)]
        for name in reversed(names):
            key = spec.field_columns.get(name, name)
            for column in spec.columns:
                if column.key == key:
                    return column.label
        return names[0].replace("_", " ").capitalize() if names else "Row"

    def _build(
        self, spec: ImportKind, number: int, values: dict[str, Any], problems: list[ImportProblem]
    ) -> BaseModel | None:
        try:
            return spec.build(values)
        except PydanticValidationError as exc:
            for error in exc.errors():
                message = str(error.get("msg", "Invalid value.")).removeprefix("Value error, ")
                problems.append(
                    ImportProblem(
                        row=number,
                        column=self._label_for(spec, tuple(error.get("loc", ()))),
                        message=message,
                    )
                )
            return None

    async def _existing(self, hospital_id: uuid.UUID, kind: str, request: Any) -> str | None:
        """Why this row is already in the hospital, or ``None`` (rule 4)."""
        if kind == "patients":
            found = await self._patient_lookup.find_same_person(
                hospital_id,
                first_name=request.first_name,
                last_name=request.last_name,
                date_of_birth=request.date_of_birth,
            )
            return f"Already registered as {found.mrn}." if found else None
        if kind == "services":
            service = await self._service_lookup.get_service_by_code(hospital_id, request.code)
            return f"Service {request.code} already exists." if service else None
        if kind == "medicines":
            medicine = await self._medicine_lookup.get_medicine_by_sku(hospital_id, request.sku)
            return f"Medicine {request.sku} already exists." if medicine else None
        test = await self._lab_test_lookup.get_test_by_code(hospital_id, request.code)
        return f"Lab test {request.code} already exists." if test else None

    @staticmethod
    def _identity(kind: str, request: Any) -> str:
        if kind == "patients":
            return (
                f"{request.first_name.strip().lower()}|{request.last_name.strip().lower()}|"
                f"{request.date_of_birth.isoformat()}"
            )
        return str(request.sku if kind == "medicines" else request.code).upper()

    async def _create(
        self, hospital_id: uuid.UUID, kind: str, request: Any, actor_id: uuid.UUID
    ) -> None:
        if kind == "patients":
            await self._patients.register_patient(hospital_id, request, actor_id=actor_id)
        elif kind == "services":
            await self._services.create_service(hospital_id, request, actor_id=actor_id)
        elif kind == "medicines":
            await self._medicines.create_medicine(hospital_id, request, actor_id=actor_id)
        else:
            await self._lab_tests.create_test(hospital_id, request, actor_id=actor_id)

    async def run(
        self,
        hospital_id: uuid.UUID,
        kind: str,
        sheet: SheetData,
        *,
        dry_run: bool,
        actor_id: uuid.UUID,
    ) -> ImportReport:
        """Validate every row and, unless a dry run, create the valid new ones (FR-2, FR-3).

        :raises UnknownImportKindError: For an unknown kind.
        """
        spec = _kind(kind)
        known = {c.key for c in spec.columns}
        missing = [c.label for c in spec.columns if c.required and c.key not in sheet.headers]
        if missing:
            return ImportReport(
                kind=kind,
                dry_run=dry_run,
                total_rows=len(sheet.rows),
                problems=[
                    ImportProblem(row=1, column=label, message="This column is missing.")
                    for label in missing
                ],
            )
        ignored = sorted({h for h in sheet.headers if h and h not in known})

        problems: list[ImportProblem] = []
        skipped: list[ImportSkip] = []
        seen: set[str] = set()
        ready = 0
        created = 0
        for number, raw in sheet.rows:
            values = self._row_values(spec, number, raw, problems)
            if values is None:
                continue
            request = self._build(spec, number, values, problems)
            if request is None:
                continue
            identity = self._identity(kind, request)
            if identity in seen:
                skipped.append(
                    ImportSkip(row=number, reason="Repeats an earlier row of this file.")
                )
                continue
            seen.add(identity)
            reason = await self._existing(hospital_id, kind, request)
            if reason:
                skipped.append(ImportSkip(row=number, reason=reason))
                continue
            ready += 1
            if dry_run:
                continue
            try:
                await self._create(hospital_id, kind, request, actor_id)
                created += 1
            except ConflictError as exc:
                skipped.append(ImportSkip(row=number, reason=exc.message))
            except AtherisError as exc:
                problems.append(ImportProblem(row=number, column="Row", message=exc.message))

        report = ImportReport(
            kind=kind,
            dry_run=dry_run,
            total_rows=len(sheet.rows),
            ready=ready,
            created=created,
            skipped=skipped,
            problems=problems,
            ignored_columns=ignored,
        )
        if not dry_run:
            await self._audit.record(
                AuditEvent(
                    action="data.import.completed",
                    hospital_id=hospital_id,
                    target_type="data_import",
                    target_id=None,
                    actor_id=actor_id,
                    context={
                        "kind": kind,
                        "rows": report.total_rows,
                        "created": created,
                        "skipped": len(skipped),
                        "problems": len(problems),
                    },
                )
            )
            await self._session.commit()
            logger.info(
                "data.import.completed",
                hospital_id=str(hospital_id),
                kind=kind,
                created=created,
                skipped=len(skipped),
                problems=len(problems),
            )
        return report
