"""Unit tests for :class:`AuthService`.

Tests business logic with mocked repositories.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.exceptions import AuthenticationError, BusinessRuleError
from app.core.security import hash_password
from app.models.user import User, UserStatus


@pytest.fixture
def mock_user_repo() -> AsyncMock:
    """Create a mock UserRepository."""
    return AsyncMock()


@pytest.fixture
def mock_refresh_token_repo() -> AsyncMock:
    """Create a mock RefreshTokenRepository."""
    return AsyncMock()


@pytest.fixture
def mock_password_reset_repo() -> AsyncMock:
    """Create a mock PasswordResetTokenRepository."""
    return AsyncMock()


@pytest.fixture
def auth_service(
    mock_user_repo: AsyncMock,
    mock_refresh_token_repo: AsyncMock,
    mock_password_reset_repo: AsyncMock,
    mock_uow: AsyncMock,
) -> Any:
    """Create an AuthService with mocked repositories."""
    from app.services.auth_service import AuthService

    return AuthService(
        user_repo=mock_user_repo,
        refresh_token_repo=mock_refresh_token_repo,
        password_reset_repo=mock_password_reset_repo,
        uow=mock_uow,
    )


def _make_user(overrides: dict[str, Any] | None = None) -> User:
    """Create a test user with sensible defaults."""
    user_id = uuid.uuid4()
    hospital_id = uuid.uuid4()
    role_id = uuid.uuid4()
    perm_id = uuid.uuid4()

    # Build a minimal user with relationships
    from app.models.permission import Permission
    from app.models.role import Role, RolePermission
    from app.models.user import UserRole

    role = MagicMock(spec=Role)
    role.id = role_id
    role.name = "Hospital Admin"
    role.description = "Test role"
    role.is_system = False
    role.hospital_id = hospital_id

    perm = MagicMock(spec=Permission)
    perm.id = perm_id
    perm.code = "user.read"
    perm.module = "auth"

    rp = MagicMock(spec=RolePermission)
    rp.permission = perm

    role.role_permissions = [rp]

    ur = MagicMock(spec=UserRole)
    ur.role = role
    ur.user_id = user_id
    ur.role_id = role_id

    user = MagicMock(spec=User)
    user.id = user_id
    user.hospital_id = hospital_id
    user.email = overrides.get("email", "test@hospital.test") if overrides else "test@hospital.test"
    user.password_hash = hash_password("TestPass@123")
    user.first_name = "Test"
    user.last_name = "User"
    user.phone = "+911234567890"
    user.status = UserStatus.ACTIVE
    user.mfa_enabled = False
    user.mfa_secret = None
    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = None
    user.password_changed_at = datetime.now(UTC)
    user.user_roles = [ur]
    user.created_at = datetime.now(UTC)
    user.updated_at = datetime.now(UTC)

    if overrides:
        for key, value in overrides.items():
            if hasattr(user, key):
                setattr(user, key, value)

    return user


# ── Login Tests ────────────────────────────────────────────────────────────


class TestLogin:
    """Tests for the login flow."""

    async def test_login_success(
        self: Any, auth_service: Any, mock_user_repo: Any, mock_refresh_token_repo: Any
    ) -> None:
        """Happy path: valid credentials return tokens."""
        user = _make_user()
        mock_user_repo.get_by_email_cross_tenant.return_value = user
        mock_refresh_token_repo.create.return_value = MagicMock(id=uuid.uuid4())

        result = await auth_service.login(
            email="test@hospital.test",
            password="TestPass@123",
        )

        assert "access_token" in result
        assert "refresh_token" in result
        assert "user" in result
        assert result["user"]["email"] == "test@hospital.test"
        mock_user_repo.record_login.assert_called_once()

    async def test_login_invalid_credentials(
        self: Any, auth_service: Any, mock_user_repo: Any
    ) -> None:
        """Invalid password returns AuthenticationError."""
        user = _make_user()
        mock_user_repo.get_by_email_cross_tenant.return_value = user

        with pytest.raises(AuthenticationError, match="Invalid credentials."):
            await auth_service.login(
                email="test@hospital.test",
                password="WrongPass@123",
            )

    async def test_login_nonexistent_email(
        self: Any, auth_service: Any, mock_user_repo: Any
    ) -> None:
        """Non-existent email returns generic error."""
        mock_user_repo.get_by_email_cross_tenant.return_value = None

        with pytest.raises(AuthenticationError, match="Invalid credentials."):
            await auth_service.login(
                email="nonexistent@test.test",
                password="SomePass@123",
            )

    async def test_login_suspended_account(
        self: Any, auth_service: Any, mock_user_repo: Any
    ) -> None:
        """Suspended account returns generic error."""
        user = _make_user({"status": UserStatus.SUSPENDED})
        mock_user_repo.get_by_email_cross_tenant.return_value = user

        with pytest.raises(AuthenticationError, match="Invalid credentials."):
            await auth_service.login(
                email="test@hospital.test",
                password="TestPass@123",
            )

    async def test_login_locked_account(self: Any, auth_service: Any, mock_user_repo: Any) -> None:
        """Locked account returns generic error."""
        user = _make_user({"locked_until": datetime.now(UTC) + timedelta(hours=1)})
        mock_user_repo.get_by_email_cross_tenant.return_value = user

        with pytest.raises(AuthenticationError, match="Invalid credentials."):
            await auth_service.login(
                email="test@hospital.test",
                password="TestPass@123",
            )


# ── Token Refresh Tests ────────────────────────────────────────────────────


class TestRefreshToken:
    """Tests for refresh token rotation."""

    async def test_refresh_success(
        self: Any, auth_service: Any, mock_user_repo: Any, mock_refresh_token_repo: Any
    ) -> None:
        """Valid refresh token returns new token pair."""
        from app.models.refresh_token import RefreshToken

        user = _make_user()
        mock_user_repo.get_by_id.return_value = user

        token = MagicMock(spec=RefreshToken)
        token.id = uuid.uuid4()
        token.user_id = user.id
        token.is_revoked = False
        token.is_expired = False
        token.is_valid = True

        mock_refresh_token_repo.get_by_token_hash.return_value = token
        mock_refresh_token_repo.create.return_value = MagicMock(id=uuid.uuid4())

        result = await auth_service.refresh_token(raw_token="some-valid-token")

        assert result["access_token"] is not None
        assert result["refresh_token"] is not None
        assert result["expires_in"] > 0

    async def test_refresh_reuse_detection(
        self: Any, auth_service: Any, mock_user_repo: Any, mock_refresh_token_repo: Any
    ) -> None:
        """Revoked token triggers reuse detection."""
        from app.models.refresh_token import RefreshToken

        user_id = uuid.uuid4()
        token = MagicMock(spec=RefreshToken)
        token.id = uuid.uuid4()
        token.user_id = user_id
        token.is_revoked = True
        token.is_expired = False

        mock_refresh_token_repo.get_by_token_hash.return_value = token

        with pytest.raises(AuthenticationError, match="has been revoked"):
            await auth_service.refresh_token(raw_token="stolen-token")

        mock_refresh_token_repo.revoke_all_for_user.assert_called_once_with(user_id)


# ── Password Reset Tests ───────────────────────────────────────────────────


class TestPasswordReset:
    """Tests for password reset flow."""

    async def test_forgot_password_existing_user(
        self: Any, auth_service: Any, mock_user_repo: Any, mock_password_reset_repo: Any
    ) -> None:
        """Existing user gets a reset token created."""
        user = _make_user()
        mock_user_repo.get_by_email_cross_tenant.return_value = user

        await auth_service.forgot_password(email="test@hospital.test")

        mock_password_reset_repo.create.assert_called_once()

    async def test_forgot_password_nonexistent_user(
        self: Any, auth_service: Any, mock_user_repo: Any, mock_password_reset_repo: Any
    ) -> None:
        """Non-existent user still returns success (no reveal)."""
        mock_user_repo.get_by_email_cross_tenant.return_value = None

        await auth_service.forgot_password(email="nonexistent@test.test")

        mock_password_reset_repo.create.assert_not_called()

    async def test_reset_password_weak_password(
        self: Any, auth_service: Any, mock_password_reset_repo: Any
    ) -> None:
        """Weak password raises BusinessRuleError."""
        with pytest.raises(BusinessRuleError, match="Password does not meet requirements"):
            await auth_service.reset_password(
                raw_token="valid-token",
                new_password="weak",
            )


# ── MFA Tests ──────────────────────────────────────────────────────────────


class TestMFA:
    """Tests for MFA enrollment and verification."""

    async def test_enroll_mfa(self: Any, auth_service: Any, mock_user_repo: Any) -> None:
        """MFA enrollment returns a secret."""
        user = _make_user()
        mock_user_repo.get_by_id.return_value = user

        result = await auth_service.enroll_mfa(
            user_id=user.id,
            password="TestPass@123",
        )

        assert "secret" in result
        assert "provisioning_uri" in result
        mock_user_repo.update.assert_called_once()
