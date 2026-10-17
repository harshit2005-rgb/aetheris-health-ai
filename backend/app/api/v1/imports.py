"""Spreadsheet import routes (``docs/modules/17-data-import-export.md`` §9).

The file is the raw request body (``Content-Type`` xlsx or csv, the name in
``X-Filename``) rather than ``multipart/form-data``, so no upload library is
needed. Routes parse input, delegate, and respond; no business logic.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Path, Query, Request, Response

from app.api.dependencies.auth import require_permission
from app.api.dependencies.services import get_import_service
from app.core.exceptions import BusinessRuleError, ValidationError
from app.models.user import User
from app.schemas.common import SuccessResponse
from app.schemas.data_import import ImportReport
from app.services.import_service import ImportService
from app.utils.spreadsheet import MAX_BYTES, XLSX_TYPE, SpreadsheetError, read_spreadsheet

router = APIRouter(prefix="/imports", tags=["Data import"])

_PERMISSION = "data.import"
_KIND_DOC = "patients, services, medicines or lab-tests."

_COMMON_RESPONSES: dict[int | str, dict[str, str]] = {
    401: {"description": "Missing or invalid access token."},
    403: {"description": "Lacking data.import."},
    404: {"description": "Unknown import kind."},
}


def _tenant_of(current_user: User) -> uuid.UUID:
    """Return the hospital the request acts within."""
    if current_user.hospital_id is None:
        msg = "This account is not scoped to a hospital, so nothing can be imported."
        raise BusinessRuleError(msg)
    return current_user.hospital_id


def _file_error(message: str) -> ValidationError:
    return ValidationError(
        message=message, detail={"errors": [{"field": "file", "message": message}]}
    )


@router.get(
    "/{kind}/template",
    response_class=Response,
    summary="Download an import template",
    description=f"A blank .xlsx with the expected columns and an instructions sheet. Kind: {_KIND_DOC}",
    responses={
        200: {"description": "The template.", "content": {XLSX_TYPE: {}}},
        **_COMMON_RESPONSES,
    },
)
async def download_template(
    kind: str = Path(description=_KIND_DOC),
    current_user: User = Depends(require_permission(_PERMISSION)),
    service: ImportService = Depends(get_import_service),
) -> Response:
    """Return the template for one kind."""
    _tenant_of(current_user)
    filename, content = service.template(kind)
    return Response(
        content=content,
        media_type=XLSX_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post(
    "/{kind}",
    response_model=SuccessResponse[ImportReport],
    summary="Import a spreadsheet",
    description=(
        "Send the .xlsx or .csv file itself as the request body, with its name in "
        "`X-Filename`. `dry_run=true` (the default) validates every row and saves "
        "nothing; `dry_run=false` creates every valid row that is not already in "
        "the hospital. Existing records are skipped, never overwritten. "
        f"Kind: {_KIND_DOC} At most 5 MB and 2,000 rows."
    ),
    responses={
        200: {"description": "The report: ready, created, skipped and problem rows."},
        422: {"description": "The file itself could not be read."},
        **_COMMON_RESPONSES,
    },
)
async def import_spreadsheet(
    request: Request,
    kind: str = Path(description=_KIND_DOC),
    dry_run: bool = Query(True, description="Validate only; save nothing."),
    filename: Annotated[str, Header(alias="X-Filename", max_length=255)] = "",
    current_user: User = Depends(require_permission(_PERMISSION)),
    service: ImportService = Depends(get_import_service),
) -> SuccessResponse[ImportReport]:
    """Validate, and unless a dry run, import one spreadsheet."""
    hospital_id = _tenant_of(current_user)
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > MAX_BYTES:
        raise _file_error("The file is larger than 5 MB. Split it into smaller files.")
    body = await request.body()
    try:
        sheet = read_spreadsheet(
            body,
            filename=filename,
            content_type=request.headers.get("content-type", ""),
        )
    except SpreadsheetError as exc:
        raise _file_error(str(exc)) from exc
    report = await service.run(hospital_id, kind, sheet, dry_run=dry_run, actor_id=current_user.id)
    message = "Checked; nothing saved." if dry_run else "Import finished."
    return SuccessResponse[ImportReport](message=message, data=report)
