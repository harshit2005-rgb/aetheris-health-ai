"""DTOs for spreadsheet import (``docs/modules/17-data-import-export.md`` §9)."""

from __future__ import annotations

from pydantic import BaseModel, Field

__all__ = ["ImportProblem", "ImportReport", "ImportSkip"]


class ImportProblem(BaseModel):
    """A row (or the header) that could not be imported, and why."""

    row: int = Field(description="Row number as the spreadsheet shows it (1 is the header).")
    column: str = Field(description="The column at fault, as the template names it.")
    message: str = Field(description="What is wrong.")


class ImportSkip(BaseModel):
    """A valid row left out because the record already exists (rule 4)."""

    row: int = Field(description="Row number as the spreadsheet shows it.")
    reason: str = Field(description="Which existing record it matches.")


class ImportReport(BaseModel):
    """What an import did, or would do on a dry run."""

    kind: str = Field(description="patients, services, medicines or lab-tests.")
    dry_run: bool = Field(description="True if nothing was saved.")
    total_rows: int = Field(description="Data rows read from the file.")
    ready: int = Field(default=0, description="Valid new rows (to be) created.")
    created: int = Field(default=0, description="Records created (0 on a dry run).")
    skipped: list[ImportSkip] = Field(default_factory=list, description="Duplicates left out.")
    problems: list[ImportProblem] = Field(default_factory=list, description="Rows with errors.")
    ignored_columns: list[str] = Field(
        default_factory=list, description="Columns in the file the template does not have."
    )
