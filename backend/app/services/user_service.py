"""User management service — create, read, update, deactivate users, manage roles.

Implements the business rules from ``docs/modules/02-user-management.md``.
Every rule is enforced here, never in the route layer.
"""

from __future__ import annotations

import math
import uuid
from typing import TYPE_CHECKING, Any

import structlog

from app.core.audit import AuditEvent
from app.core.exceptions import BusinessRuleError, NotFoundError, PermissionDeniedError
from app.core.security import hash_password
from app.models.user import User, UserStatus

if TYPE_CHECKING:
    from app.core.audit import AuditSink
    from app.database.unit_of_work import UnitOfWork
    from app.repositories.permission_repository import PermissionRepository
    from app.repositories.role_repository import RoleRepository
    from app.repositories.user_repository import UserRepository
    from app.services.auth_service import AuthService

logger = structlog.get_logger(__name__)


class UserService:
    """Handles user lifecycle and role management.

    :param user_repo: Repository for user data access.
    :param role_repo: Repository for role data access.
    :param permission_repo: Repository for permission data access.
    :param auth_service: Auth service for token revocation.
    :param audit: Where mutating operations are recorded (CLAUDE.md rule 9).
    """

    def __init__(
        self,
        user_repo: UserRepository,
        role_repo: RoleRepository,
        permission_repo: PermissionRepository,
        auth_service: AuthService,
        uow: UnitOfWork,
        audit: AuditSink,
    ) -> None:
        self._user_repo = user_repo
        self._role_repo = role_repo
        self._permission_repo = permission_repo
        self._auth_service = auth_service
        self._uow = uow
        self._audit = audit

    # ── Read ─────────────────────────────────────────────────────────────────

    async def get_user(
        self, user_id: uuid.UUID, actor_hospital_id: uuid.UUID | None = None
    ) -> User:
        """Retrieve a single user by ID.

        :param user_id: The user's UUID.
        :param actor_hospital_id: The hospital ID of the requesting user for isolation.
        :returns: The user instance.
        :raises NotFoundError: If the user doesn't exist or is soft-deleted.
        :raises PermissionDeniedError: If cross-hospital access is attempted.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        # Multi-tenant isolation: ensure user belongs to the same hospital
        if actor_hospital_id is not None and user.hospital_id != actor_hospital_id:
            raise NotFoundError("User not found.")

        return user

    async def list_users(
        self,
        hospital_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 25,
        status: UserStatus | None = None,
        search: str | None = None,
    ) -> dict[str, Any]:
        """List users in a hospital with pagination and optional filters.

        :param hospital_id: The hospital UUID for tenant isolation.
        :param page: 1-based page number.
        :param page_size: Records per page (max 100).
        :param status: Optional status filter.
        :param search: Optional search query for name/email.
        :returns: Dict with ``items``, ``total``, ``page``, ``page_size``, ``total_pages``.
        """
        limit = min(page_size, 100)
        offset = (page - 1) * limit

        # Get users with filters
        users = await self._user_repo.list_by_hospital(
            hospital_id,
            skip=offset,
            limit=limit,
            status=status,
            search=search,
        )

        total = await self._user_repo.count_by_hospital(hospital_id, status=status)

        # Enrich with roles
        user_list = []
        for u in users:
            roles = [
                {
                    "id": r.role.id,
                    "name": r.role.name,
                    "description": r.role.description,
                    "is_system": r.role.is_system,
                }
                for r in (u.user_roles or [])
            ]
            user_list.append(
                {
                    "id": u.id,
                    "email": u.email,
                    "first_name": u.first_name,
                    "last_name": u.last_name,
                    "phone": u.phone,
                    "status": u.status.value,
                    "hospital_id": u.hospital_id,
                    "roles": roles,
                    "mfa_enabled": u.mfa_enabled,
                    "last_login_at": u.last_login_at,
                    "password_changed_at": u.password_changed_at,
                    "created_at": u.created_at,
                    "updated_at": u.updated_at,
                }
            )

        return {
            "items": user_list,
            "total": total,
            "page": page,
            "page_size": limit,
            "total_pages": math.ceil(total / limit) if limit > 0 else 0,
        }

    async def get_current_user_profile(self, user_id: uuid.UUID) -> User:
        """Get the current user's full profile.

        :param user_id: The user's UUID.
        :returns: The user instance.
        :raises NotFoundError: If the user doesn't exist.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    # ── Create / Invite ──────────────────────────────────────────────────────

    async def invite_user(
        self,
        hospital_id: uuid.UUID,
        email: str,
        first_name: str,
        last_name: str,
        phone: str | None = None,
        role_ids: list[uuid.UUID] | None = None,
        actor_permissions: list[str] | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> User:
        """Invite a new user to the system.

        Creates the user with ``status=invited``. The user will need to
        set their password via the invitation link.

        :param hospital_id: The hospital UUID.
        :param email: The user's email address.
        :param first_name: The user's given name.
        :param last_name: The user's family name.
        :param phone: Optional phone number.
        :param role_ids: Optional list of initial role UUIDs.
        :param actor_permissions: Permissions of the actor performing the invite.
        :param actor_id: UUID of the acting user, for the audit trail.
        :returns: The created user instance.
        :raises BusinessRuleError: If the email already exists in the hospital.
        :raises PermissionDeniedError: If the actor doesn't have ``user.create``.
        """
        # Check permission
        if not actor_permissions or "user.create" not in actor_permissions:
            raise PermissionDeniedError("You do not have permission to create users.")

        # Check for duplicate email
        existing = await self._user_repo.get_by_email(hospital_id, email)
        if existing is not None:
            raise BusinessRuleError("A user with this email already exists in this hospital.")

        # Create user without a password (they'll set it via the invite link)
        user = await self._user_repo.create(
            hospital_id=hospital_id,
            email=email,
            password_hash=hash_password(uuid.uuid4().hex),  # placeholder password
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            status=UserStatus.INVITED,
        )

        # Assign roles if provided
        if role_ids:
            for role_id in role_ids:
                role = await self._role_repo.get_by_id(role_id)
                if role is None:
                    continue
                # Check if already assigned
                if not await self._user_repo.has_role(user.id, role_id):
                    await self._user_repo.add_role(user.id, role_id)

        await self._audit.record(
            AuditEvent(
                action="user.invited",
                hospital_id=hospital_id,
                target_type="user",
                target_id=user.id,
                actor_id=actor_id,
            )
        )
        await self._uow.commit()
        logger.info("user_invited", user_id=str(user.id), hospital_id=str(hospital_id))
        return user

    # ── Update ───────────────────────────────────────────────────────────────

    async def update_user(
        self,
        user_id: uuid.UUID,
        actor_hospital_id: uuid.UUID | None = None,
        actor_permissions: list[str] | None = None,
        actor_id: uuid.UUID | None = None,
        **updates: Any,
    ) -> User:
        """Update a user's profile fields.

        :param user_id: The user's UUID.
        :param actor_hospital_id: The hospital ID of the requesting user.
        :param actor_permissions: Permissions of the actor.
        :param actor_id: UUID of the acting user, for the audit trail.
        :param updates: Fields to update (first_name, last_name, phone).
        :returns: The updated user instance.
        :raises NotFoundError: If the user doesn't exist.
        :raises PermissionDeniedError: If the actor doesn't have ``user.update``.
        """
        user = await self.get_user(user_id, actor_hospital_id)

        if actor_permissions and "user.update" not in actor_permissions:
            raise PermissionDeniedError("You do not have permission to update users.")

        # Only allow updating allowed fields
        allowed_fields = {"first_name", "last_name", "phone"}
        safe_updates = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}

        if safe_updates:
            user = await self._user_repo.update(user, **safe_updates)
            await self._audit.record(
                AuditEvent(
                    action="user.updated",
                    hospital_id=user.hospital_id,
                    target_type="user",
                    target_id=user.id,
                    actor_id=actor_id,
                    # Field *names* only — never values, per the audit PII rule
                    # (docs/07-SECURITY.md, rule 10).
                    changes={field: {"before": None, "after": None} for field in safe_updates},
                )
            )
            await self._uow.commit()
            logger.info("user_updated", user_id=str(user.id), fields=list(safe_updates.keys()))

        return user

    async def update_own_profile(self, user_id: uuid.UUID, **updates: Any) -> User:
        """Update the current user's own profile.

        :param user_id: The user's UUID.
        :param updates: Fields to update (first_name, last_name, phone).
        :returns: The updated user instance.
        """
        user = await self.get_user(user_id)

        allowed_fields = {"first_name", "last_name", "phone"}
        safe_updates = {k: v for k, v in updates.items() if k in allowed_fields and v is not None}

        if safe_updates:
            user = await self._user_repo.update(user, **safe_updates)
            await self._audit.record(
                AuditEvent(
                    action="user.updated",
                    hospital_id=user.hospital_id,
                    target_type="user",
                    target_id=user.id,
                    actor_id=user_id,
                    changes={field: {"before": None, "after": None} for field in safe_updates},
                )
            )
            await self._uow.commit()
            logger.info("own_profile_updated", user_id=str(user.id))

        return user

    # ── Deactivate / Reactivate ──────────────────────────────────────────────

    async def deactivate_user(self, user_id: uuid.UUID, actor_user_id: uuid.UUID) -> User:
        """Deactivate (suspend) a user.

        :param user_id: The user's UUID.
        :param actor_user_id: The UUID of the user performing the action.
        :returns: The updated user instance.
        :raises BusinessRuleError: If trying to deactivate oneself.
        :raises NotFoundError: If the user doesn't exist.
        """
        if user_id == actor_user_id:
            raise BusinessRuleError("You cannot deactivate yourself.")

        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        await self._user_repo.update(user, status=UserStatus.SUSPENDED)

        # Revoke all sessions
        await self._auth_service.logout_all(user_id)

        await self._audit.record(
            AuditEvent(
                action="user.deactivated",
                hospital_id=user.hospital_id,
                target_type="user",
                target_id=user.id,
                actor_id=actor_user_id,
            )
        )
        await self._uow.commit()
        logger.info("user_deactivated", user_id=str(user_id), actor_id=str(actor_user_id))
        return user

    async def reactivate_user(self, user_id: uuid.UUID, *, actor_id: uuid.UUID | None = None) -> User:
        """Reactivate a suspended user.

        :param user_id: The user's UUID.
        :param actor_id: UUID of the acting user, for the audit trail.
        :returns: The updated user instance.
        :raises NotFoundError: If the user doesn't exist.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        await self._user_repo.update(
            user, status=UserStatus.ACTIVE, failed_login_attempts=0, locked_until=None
        )

        await self._audit.record(
            AuditEvent(
                action="user.reactivated",
                hospital_id=user.hospital_id,
                target_type="user",
                target_id=user.id,
                actor_id=actor_id,
            )
        )
        await self._uow.commit()
        logger.info("user_reactivated", user_id=str(user_id))
        return user

    # ── Role Management ──────────────────────────────────────────────────────

    async def assign_role(
        self,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        actor_permissions: list[str] | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> User:
        """Assign a role to a user.

        :param user_id: The user's UUID.
        :param role_id: The role's UUID.
        :param actor_permissions: Permissions of the actor.
        :param actor_id: UUID of the acting user, for the audit trail.
        :returns: The updated user instance.
        :raises PermissionDeniedError: If the actor doesn't have ``role.assign``.
        :raises NotFoundError: If the user or role doesn't exist.
        """
        if actor_permissions and "role.assign" not in actor_permissions:
            raise PermissionDeniedError("You do not have permission to assign roles.")

        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        role = await self._role_repo.get_by_id(role_id)
        if role is None:
            raise NotFoundError("Role not found.")

        # Check if already assigned
        if await self._user_repo.has_role(user_id, role_id):
            logger.info("role_already_assigned", user_id=str(user_id), role_id=str(role_id))
            return user

        # Assign the role
        await self._user_repo.add_role(user_id, role_id)

        # Revoke refresh tokens to force re-login with new claims
        await self._auth_service.logout_all(user_id)

        await self._audit.record(
            AuditEvent(
                action="role.assigned",
                hospital_id=user.hospital_id,
                target_type="user",
                target_id=user.id,
                actor_id=actor_id,
                changes={"role_id": {"before": None, "after": str(role_id)}},
            )
        )
        await self._uow.commit()
        logger.info("role_assigned", user_id=str(user_id), role_id=str(role_id))
        return user

    async def remove_role(
        self,
        user_id: uuid.UUID,
        role_id: uuid.UUID,
        actor_permissions: list[str] | None = None,
        actor_id: uuid.UUID | None = None,
    ) -> User:
        """Remove a role from a user.

        :param user_id: The user's UUID.
        :param role_id: The role's UUID.
        :param actor_permissions: Permissions of the actor.
        :param actor_id: UUID of the acting user, for the audit trail.
        :returns: The updated user instance.
        :raises PermissionDeniedError: If the actor doesn't have ``role.assign``.
        :raises NotFoundError: If the user doesn't exist.
        """
        if actor_permissions and "role.assign" not in actor_permissions:
            raise PermissionDeniedError("You do not have permission to remove roles.")

        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        removed = await self._user_repo.remove_role(user_id, role_id)
        if removed:
            await self._auth_service.logout_all(user_id)
            await self._audit.record(
                AuditEvent(
                    action="role.removed",
                    hospital_id=user.hospital_id,
                    target_type="user",
                    target_id=user.id,
                    actor_id=actor_id,
                    changes={"role_id": {"before": str(role_id), "after": None}},
                )
            )
            await self._uow.commit()
            logger.info("role_removed", user_id=str(user_id), role_id=str(role_id))

        return user

    async def list_user_roles(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        """List all roles assigned to a user.

        :param user_id: The user's UUID.
        :returns: List of role dicts.
        :raises NotFoundError: If the user doesn't exist.
        """
        user = await self._user_repo.get_by_id(user_id)
        if user is None:
            raise NotFoundError("User not found.")

        return [
            {
                "id": r.role.id,
                "name": r.role.name,
                "description": r.role.description,
                "is_system": r.role.is_system,
            }
            for r in (user.user_roles or [])
        ]
