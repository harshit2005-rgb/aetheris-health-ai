"""Who the seed lets download invoice PDFs (``GET /invoices/{id}/pdf``).

The seed silently skips a code it does not recognise in a role's list, so a
typo would not fail ``make seed``: it would leave the cashier unable to print a
bill. These tests read the seed's own tables and fail on exactly that.
"""

from __future__ import annotations

import pytest

from app.seeds.seed import PERMISSION_DEFINITIONS, SYSTEM_ROLES

PDF = "invoice.pdf.download"

#: The roles that print bills: the admins, and the cashier at the counter
#: (founder's decision, 2026-10-16). Nobody else.
EXPECTED = {"Super Admin", "Hospital Admin", "Billing Staff"}


def test_the_code_is_in_the_catalog() -> None:
    assert PDF in {code for code, _, _ in PERMISSION_DEFINITIONS}


@pytest.mark.parametrize(("role", "codes"), [(name, codes) for name, _, codes in SYSTEM_ROLES])
def test_only_the_billing_roles_download_pdfs(role: str, codes: list[str]) -> None:
    assert (PDF in codes) is (role in EXPECTED)


def test_every_role_that_downloads_pdfs_can_read_invoices() -> None:
    # The PDF route needs the code alone, but a role that can print a bill it
    # cannot open would be a broken screen.
    for name, _, codes in SYSTEM_ROLES:
        if PDF in codes:
            assert {"invoice.read", "invoice.read.own"} & set(codes), name
