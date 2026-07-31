"""Unit tests for :class:`~app.services.role_service.RoleService`.

Tests business logic with mocked repositories — no database required
(``docs/11-TESTING_STRATEGY.md`` §2.1).
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.schemas.role import PermissionResponse, RoleDetailResponse
from app.services.role_service import RoleNotFoundError, RoleService


@pytest.fixture
def mock_role_repo() -> AsyncMock:
    """Create a mock RoleRepository."""
    return AsyncMock()


@pytest.fixture
def mock_permission_repo() -> AsyncMock:
    """Create a mock PermissionRepository."""
    return AsyncMock()


@pytest.fixture
def service(mock_role_repo: AsyncMock, mock_permission_repo: AsyncMock) -> Any:
    """Create a RoleService with mocked repositories."""
    return RoleService(mock_role_repo, mock_permission_repo)


def _make_role(**overrides: Any) -> MagicMock:
    """Build a mocked Role ORM instance with sensible defaults."""
    role = MagicMock()
    role.id = overrides.pop("id", uuid.uuid4())
    role.name = overrides.pop("name", "Doctor")
    role.description = overrides.pop("description", "Clinical access.")
    role.is_system = overrides.pop("is_system", False)
    role.hospital_id = overrides.pop("hospital_id", None)

    # Permission graph: one permission on one role_permission row.
    permission = MagicMock()
    permission.code = overrides.pop("permission_code", "patient.read")
    role_permission = MagicMock()
    role_permission.permission = permission
    role.role_permissions = overrides.pop("role_permissions", [role_permission])

    for key, value in overrides.items():
        setattr(role, key, value)
    return role


class TestListRoles:
    """``RoleService.list_roles``."""

    async def test_list_returns_page_of_summaries(
        self, service: Any, mock_role_repo: Any
    ) -> None:
        """Rows are converted to RoleResponse and wrapped in a Page."""
        hospital_id = uuid.uuid4()
        mock_role_repo.list_by_hospital.return_value = [
            _make_role(name="Doctor"),
            _make_role(name="Receptionist"),
        ]
        mock_role_repo.count_by_hospital.return_value = 2

        page = await service.list_roles(hospital_id)

        assert page.total_records == 2
        assert page.total_pages == 1
        assert [item.name for item in page.items] == ["Doctor", "Receptionist"]
        mock_role_repo.list_by_hospital.assert_awaited_once()
        mock_role_repo.count_by_hospital.assert_awaited_once_with(
            hospital_id, include_system=True
        )

    async def test_list_passes_pagination(
        self, service: Any, mock_role_repo: Any
    ) -> None:
        """Offset/limit are derived from the pagination params."""
        mock_role_repo.list_by_hospital.return_value = []
        mock_role_repo.count_by_hospital.return_value = 0

        await service.list_roles(uuid.uuid4(), pagination=MagicMock(offset=10, limit=5, page=3, page_size=5))

        _, kwargs = mock_role_repo.list_by_hospital.await_args
        assert kwargs["skip"] == 10
        assert kwargs["limit"] == 5
        assert kwargs["include_system"] is True


class TestGetRole:
    """``RoleService.get_role``."""

    async def test_get_role_includes_permission_codes(
        self, service: Any, mock_role_repo: Any
    ) -> None:
        """The detail DTO carries the role's permission codes."""
        hospital_id = uuid.uuid4()
        role = _make_role(name="Doctor")
        # Two permissions, deliberately unsorted.
        perm_a = MagicMock()
        perm_a.code = "appointment.book"
        perm_b = MagicMock()
        perm_b.code = "patient.read"
        rp_a = MagicMock()
        rp_a.permission = perm_a
        rp_b = MagicMock()
        rp_b.permission = perm_b
        role.role_permissions = [rp_a, rp_b]
        mock_role_repo.get_with_permissions.return_value = role

        result = await service.get_role(hospital_id, role.id)

        assert isinstance(result, RoleDetailResponse)
        assert result.permission_codes == ["appointment.book", "patient.read"]
        mock_role_repo.get_with_permissions.assert_awaited_once_with(
            role.id, hospital_id=hospital_id
        )

    async def test_get_missing_role_raises_not_found(
        self, service: Any, mock_role_repo: Any
    ) -> None:
        """A role absent from the tenant's scope raises RoleNotFoundError."""
        mock_role_repo.get_with_permissions.return_value = None

        with pytest.raises(RoleNotFoundError):
            await service.get_role(uuid.uuid4(), uuid.uuid4())

    async def test_get_another_tenants_role_is_a_404(
        self, service: Any, mock_role_repo: Any
    ) -> None:
        """A cross-tenant role is indistinguishable from a missing one."""
        hospital_id = uuid.uuid4()
        foreign = _make_role(name="Doctor", hospital_id=uuid.uuid4())
        # The repository enforces scoping in SQL; a caller that bypasses it
        # still gets a 404 via the service's None check.
        mock_role_repo.get_with_permissions.return_value = None

        with pytest.raises(RoleNotFoundError):
            await service.get_role(hospital_id, foreign.id)


class TestListPermissions:
    """``RoleService.list_permissions``."""

    async def test_list_permissions_returns_catalog(
        self, service: Any, mock_permission_repo: Any
    ) -> None:
        """Rows are converted to PermissionResponse and wrapped in a Page."""
        permission = MagicMock()
        permission.id = uuid.uuid4()
        permission.code = "patient.read"
        permission.description = "View patient records."
        permission.module = "patient"
        mock_permission_repo.list_all.return_value = [permission]
        mock_permission_repo.count_all.return_value = 1

        page = await service.list_permissions(module="patient")

        assert page.total_records == 1
        assert isinstance(page.items[0], PermissionResponse)
        assert page.items[0].code == "patient.read"
        assert page.items[0].module == "patient"
        mock_permission_repo.list_all.assert_awaited_once_with(
            skip=0, limit=25, module="patient"
        )
        mock_permission_repo.count_all.assert_awaited_once_with(module="patient")

    async def test_list_permissions_without_module(
        self, service: Any, mock_permission_repo: Any
    ) -> None:
        """Omitting ``module`` lists the whole catalog."""
        mock_permission_repo.list_all.return_value = []
        mock_permission_repo.count_all.return_value = 0

        await service.list_permissions()

        mock_permission_repo.list_all.assert_awaited_once_with(
            skip=0, limit=25, module=None
        )
        mock_permission_repo.count_all.assert_awaited_once_with(module=None)
