"""Unit tests for :class:`UserService`.

Tests business logic with mocked repositories.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import BusinessRuleError, NotFoundError
from app.models.user import User, UserStatus


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Create a mock UserRepository."""
    return AsyncMock()


@pytest.fixture
def mock_role_repo() -> AsyncMock:
    """Create a mock RoleRepository."""
    return AsyncMock()


@pytest.fixture
def mock_permission_repo() -> AsyncMock:
    """Create a mock PermissionRepository."""
    return AsyncMock()


@pytest.fixture
def mock_auth_service() -> AsyncMock:
    """Create a mock AuthService."""
    return AsyncMock()


@pytest.fixture
def user_service(
    mock_user_repo: AsyncMock,
    mock_role_repo: AsyncMock,
    mock_permission_repo: AsyncMock,
    mock_auth_service: AsyncMock,
) -> Any:
    """Create a UserService with mocked dependencies."""
    from app.services.user_service import UserService

    return UserService(
        user_repo=mock_user_repo,
        role_repo=mock_role_repo,
        permission_repo=mock_permission_repo,
        auth_service=mock_auth_service,
    )


def _make_user(overrides: dict[str, Any] | None = None) -> User:
    """Create a test user with sensible defaults."""
    user_id = uuid.uuid4()
    hospital_id = uuid.uuid4()

    user = MagicMock(spec=User)
    user.id = user_id
    user.hospital_id = hospital_id
    user.email = "test@hospital.test"
    user.first_name = "Test"
    user.last_name = "User"
    user.phone = "+911234567890"
    user.status = UserStatus.ACTIVE
    user.mfa_enabled = False
    user.user_roles = []
    user.created_at = MagicMock()
    user.updated_at = MagicMock()

    if overrides:
        for key, value in overrides.items():
            if hasattr(user, key):
                setattr(user, key, value)

    return user


# ── Read Tests ─────────────────────────────────────────────────────────────

class TestGetUser:
    """Tests for retrieving users."""

    async def test_get_user_success(self: Any, user_service: Any, mock_user_repo: Any) -> None:
        """Existing user is returned."""
        user = _make_user()
        mock_user_repo.get_by_id.return_value = user

        result = await user_service.get_user(user_id=user.id)
        assert result.id == user.id
        assert result.email == "test@hospital.test"

    async def test_get_user_not_found(self: Any, user_service: Any, mock_user_repo: Any) -> None:
        """Non-existent user raises NotFoundError."""
        mock_user_repo.get_by_id.return_value = None

        with pytest.raises(NotFoundError, match="User not found."):
            await user_service.get_user(user_id=uuid.uuid4())

    async def test_get_user_cross_hospital_blocked(self: Any, user_service: Any, mock_user_repo: Any) -> None:
        """User from different hospital is not visible."""
        user = _make_user()
        mock_user_repo.get_by_id.return_value = user

        other_hospital_id = uuid.uuid4()
        with pytest.raises(NotFoundError, match="User not found."):
            await user_service.get_user(user_id=user.id, actor_hospital_id=other_hospital_id)


# ── Invite Tests ──────────────────────────────────────────────────────────

class TestInviteUser:
    """Tests for inviting users."""

    async def test_invite_user_success(self: Any, user_service: Any, mock_user_repo: Any) -> None:
        """User is created with invited status."""
        hospital_id = uuid.uuid4()
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.create.return_value = _make_user({
            "status": UserStatus.INVITED,
            "hospital_id": hospital_id,
        })

        result = await user_service.invite_user(
            hospital_id=hospital_id,
            email="newuser@hospital.test",
            first_name="New",
            last_name="User",
            actor_permissions=["user.create"],
        )

        assert result.status == UserStatus.INVITED
        mock_user_repo.create.assert_called_once()

    async def test_invite_user_duplicate_email(self: Any, user_service: Any, mock_user_repo: Any) -> None:
        """Duplicate email raises BusinessRuleError."""
        hospital_id = uuid.uuid4()
        mock_user_repo.get_by_email.return_value = _make_user()

        with pytest.raises(BusinessRuleError, match="already exists"):
            await user_service.invite_user(
                hospital_id=hospital_id,
                email="existing@hospital.test",
                first_name="Existing",
                last_name="User",
                actor_permissions=["user.create"],
            )

    async def test_invite_user_without_permission(self: Any, user_service: Any, mock_user_repo: Any) -> None:
        """Missing permission raises error."""
        from app.core.exceptions import PermissionDeniedError

        # Ensure get_by_email returns None so it won't interfere
        mock_user_repo.get_by_email.return_value = None

        with pytest.raises(PermissionDeniedError, match="do not have permission"):
            await user_service.invite_user(
                hospital_id=uuid.uuid4(),
                email="test@hospital.test",
                first_name="Test",
                last_name="User",
                actor_permissions=[],
            )


# ── Deactivate Tests ──────────────────────────────────────────────────────

class TestDeactivateUser:
    """Tests for deactivating users."""

    async def test_deactivate_other_user(self: Any, user_service: Any, mock_user_repo: Any, mock_auth_service: Any) -> None:
        """Admin can deactivate another user."""
        user = _make_user()
        admin_id = uuid.uuid4()
        mock_user_repo.get_by_id.return_value = user

        # Mock update to modify the user in-place (simulating SQLAlchemy flush)
        async def _update_in_place(instance: Any, **kwargs: Any) -> Any:
            for key, value in kwargs.items():
                setattr(instance, key, value)
            return instance

        mock_user_repo.update.side_effect = _update_in_place

        result = await user_service.deactivate_user(user_id=user.id, actor_user_id=admin_id)

        assert result.status == UserStatus.SUSPENDED
        mock_auth_service.logout_all.assert_called_once_with(user.id)

    async def test_deactivate_self_raises_error(self: Any, user_service: Any, mock_user_repo: Any) -> None:
        """Deactivating yourself is not allowed."""
        user = _make_user()

        with pytest.raises(BusinessRuleError, match="cannot deactivate yourself"):
            await user_service.deactivate_user(user_id=user.id, actor_user_id=user.id)


# ── Role Management Tests ──────────────────────────────────────────────────

class TestRoleManagement:
    """Tests for role assignment and removal."""

    async def test_assign_role(self: Any, user_service: Any, mock_user_repo: Any, mock_role_repo: Any, mock_auth_service: Any) -> None:
        """Role is assigned and sessions are revoked."""
        user = _make_user()
        role_id = uuid.uuid4()

        mock_user_repo.get_by_id.return_value = user
        mock_role_repo.get_by_id.return_value = MagicMock(id=role_id, name="Doctor")
        mock_user_repo.has_role.return_value = False

        await user_service.assign_role(
            user_id=user.id,
            role_id=role_id,
            actor_permissions=["role.assign"],
        )

        mock_user_repo.add_role.assert_called_once_with(user.id, role_id)
        mock_auth_service.logout_all.assert_called_once_with(user.id)

    async def test_assign_role_already_assigned(self: Any, user_service: Any, mock_user_repo: Any, mock_role_repo: Any, mock_auth_service: Any) -> None:
        """Re-assigning same role is idempotent."""
        user = _make_user()
        role_id = uuid.uuid4()

        mock_user_repo.get_by_id.return_value = user
        mock_role_repo.get_by_id.return_value = MagicMock(id=role_id, name="Doctor")
        mock_user_repo.has_role.return_value = True  # Already assigned

        await user_service.assign_role(
            user_id=user.id,
            role_id=role_id,
            actor_permissions=["role.assign"],
        )

        mock_user_repo.add_role.assert_not_called()

    async def test_remove_role(self: Any, user_service: Any, mock_user_repo: Any, mock_auth_service: Any) -> None:
        """Role is removed and sessions are revoked."""
        user = _make_user()
        role_id = uuid.uuid4()

        mock_user_repo.get_by_id.return_value = user
        mock_user_repo.remove_role.return_value = True  # Successfully removed

        await user_service.remove_role(
            user_id=user.id,
            role_id=role_id,
            actor_permissions=["role.assign"],
        )

        mock_user_repo.remove_role.assert_called_once_with(user.id, role_id)
        mock_auth_service.logout_all.assert_called_once_with(user.id)
