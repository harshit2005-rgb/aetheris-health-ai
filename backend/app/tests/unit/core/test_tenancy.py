"""Unit tests for :mod:`app.core.tenancy` and the repository tenancy contract.

No database. The second half is a structural guard over every repository: a
method that could run without a tenant fails here until someone classifies it.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import pkgutil
import uuid
from typing import Any

import pytest

import app.models  # noqa: F401 — registers every mapper
import app.repositories as repositories_package
from app.core.tenancy import (
    CrossTenant,
    TenantScope,
    TenantScopeRequiredError,
    bind_tenant_scope,
    cross_tenant,
    current_tenant_scope,
    is_tenant_scoped,
    scope_for_principal,
    tenant_column_nullable,
    tenant_or_platform,
    tenant_scope,
)
from app.database import Base
from app.repositories.base import BaseRepository
from app.repositories.report_repository import ReportRepository


class TestMarkers:
    def test_cross_tenant_needs_a_reason(self) -> None:
        with pytest.raises(ValueError, match="needs a reason"):
            cross_tenant("")
        with pytest.raises(ValueError, match="needs a reason"):
            cross_tenant("   ")

    def test_cross_tenant_carries_its_reason(self) -> None:
        marker = cross_tenant("login: tenant not known yet")
        assert isinstance(marker, CrossTenant)
        assert marker.reason == "login: tenant not known yet"

    def test_tenant_or_platform_keeps_a_hospital(self) -> None:
        hospital_id = uuid.uuid4()
        assert tenant_or_platform(hospital_id, reason="x") == hospital_id

    def test_tenant_or_platform_makes_the_platform_branch_explicit(self) -> None:
        scope = tenant_or_platform(None, reason="platform administrator")
        assert isinstance(scope, CrossTenant)
        assert scope.reason == "platform administrator"


class TestTenantScope:
    def test_a_hospital_scope_needs_a_hospital(self) -> None:
        with pytest.raises(TenantScopeRequiredError):
            TenantScope.hospital(None)  # type: ignore[arg-type]

    def test_a_system_scope_needs_a_reason(self) -> None:
        with pytest.raises(ValueError, match="needs a reason"):
            TenantScope.system("")

    def test_a_staff_principal_is_confined_to_its_hospital(self) -> None:
        hospital_id = uuid.uuid4()
        scope = scope_for_principal(hospital_id)
        assert scope.hospital_id == hospital_id
        assert not scope.is_system

    def test_a_platform_principal_gets_an_explicit_system_scope(self) -> None:
        scope = scope_for_principal(None)
        assert scope.is_system
        assert scope.reason

    def test_nothing_is_bound_by_default(self) -> None:
        assert current_tenant_scope() is None

    def test_a_scope_block_restores_the_previous_scope(self) -> None:
        outer, inner = uuid.uuid4(), uuid.uuid4()
        with tenant_scope(TenantScope.hospital(outer)):
            with tenant_scope(TenantScope.hospital(inner)):
                assert current_tenant_scope() == TenantScope.hospital(inner)
            assert current_tenant_scope() == TenantScope.hospital(outer)
        assert current_tenant_scope() is None

    def test_a_scope_block_is_restored_when_the_block_raises(self) -> None:
        with (
            pytest.raises(RuntimeError, match="boom"),
            tenant_scope(TenantScope.hospital(uuid.uuid4())),
        ):
            raise RuntimeError("boom")
        assert current_tenant_scope() is None

    async def test_a_bound_scope_does_not_outlive_its_task(self) -> None:
        """What a request dependency binds is gone when the request's task ends."""

        async def _request() -> None:
            bind_tenant_scope(TenantScope.hospital(uuid.uuid4()))
            assert current_tenant_scope() is not None

        await asyncio.create_task(_request())

        assert current_tenant_scope() is None


class TestModelClassification:
    def test_tables_with_a_hospital_column_are_tenant_scoped(self) -> None:
        from app.models.patient import Patient
        from app.models.permission import Permission
        from app.models.refresh_token import RefreshToken

        assert is_tenant_scoped(Patient)
        assert not is_tenant_scoped(Permission)
        assert not is_tenant_scoped(RefreshToken)

    def test_only_roles_and_audit_logs_allow_a_row_with_no_hospital(self) -> None:
        nullable = {
            mapper.class_.__tablename__
            for mapper in Base.registry.mappers
            if is_tenant_scoped(mapper.class_) and tenant_column_nullable(mapper.class_)
        }
        assert nullable == {"roles", "audit_logs"}


# ── Structural guard over every repository ──────────────────────────────────

#: Public repository methods on tenant-scoped models that neither take a
#: hospital nor an already-loaded row. Each is a deliberate decision with its
#: reason. A new one fails ``test_every_tenant_repository_method_is_classified``
#: until it is added here — which is the point.
EXPLICIT_EXCEPTIONS: dict[str, str] = {
    "AppointmentRepository.find_no_show_candidates": (
        "Scheduled job. Run under TenantScope.system; each row is then handled "
        "under its own hospital."
    ),
    "NotificationRepository.claim_due_deliveries": (
        "Scheduled job. Run under TenantScope.system; each row is then handled "
        "under its own hospital."
    ),
    "NotificationRepository.get_preferences": (
        "notification_preferences is keyed by user and has no hospital column."
    ),
    "NotificationRepository.get_preferences_for_users": (
        "notification_preferences is keyed by user; the users were resolved inside a hospital."
    ),
    "NotificationRepository.save_preferences": (
        "notification_preferences is keyed by user and has no hospital column."
    ),
    "UserRepository.get_by_email_cross_tenant": (
        "Login and password reset: the hospital is unknown until the account is found."
    ),
    "UserRepository.has_role": "user_roles has no hospital column; the service scopes both ends.",
    "UserRepository.add_role": "user_roles has no hospital column; the service scopes both ends.",
    "UserRepository.remove_role": (
        "user_roles has no hospital column; the service scopes both ends."
    ),
}

#: Parameters that carry the tenant into a repository method.
_TENANT_PARAMETERS = {"hospital_id", "scope"}


def _all_repositories() -> list[type[BaseRepository[Any]]]:
    for module in pkgutil.iter_modules(repositories_package.__path__):
        importlib.import_module(f"{repositories_package.__name__}.{module.name}")

    found: set[type[BaseRepository[Any]]] = set()

    def _walk(cls: type[BaseRepository[Any]]) -> None:
        for subclass in cls.__subclasses__():
            found.add(subclass)
            _walk(subclass)

    _walk(BaseRepository)
    return sorted(found, key=lambda cls: cls.__name__)


def _model_of(repository: type[BaseRepository[Any]]) -> type[Any]:
    """Return the model a repository manages, by building it on a null session."""
    instance = repository(None)  # type: ignore[call-arg, arg-type]
    return instance._model  # noqa: SLF001 — the guard needs the managed model


def _public_methods(cls: type[Any]) -> list[tuple[str, Any]]:
    return [
        (name, member)
        for name, member in vars(cls).items()
        if not name.startswith("_") and inspect.iscoroutinefunction(member)
    ]


def _unclassified(cls: type[Any], model_names: set[str]) -> list[str]:
    """List methods that take neither a tenant nor an already-loaded row."""
    missing: list[str] = []
    for name, member in _public_methods(cls):
        parameters = list(inspect.signature(member).parameters.values())[1:]
        if any(parameter.name in _TENANT_PARAMETERS for parameter in parameters):
            continue
        # A method whose first argument is an ORM instance acts on a row that a
        # tenant-scoped read already returned; the session guard still refuses
        # it if that row belongs to another hospital.
        if parameters and str(parameters[0].annotation) in model_names:
            continue
        missing.append(f"{cls.__name__}.{name}")
    return missing


class TestRepositoryContract:
    def test_every_repository_is_discovered(self) -> None:
        # 23 BaseRepository subclasses today; the guard below is only as good
        # as this discovery, so a silent drop to zero must fail loudly.
        assert len(_all_repositories()) >= 23

    def test_every_tenant_repository_method_is_classified(self) -> None:
        """No public method on a tenant-scoped repository can run without a tenant.

        It must take ``hospital_id`` (or ``scope``), or act on an already-loaded
        row, or be listed in ``EXPLICIT_EXCEPTIONS`` with a reason.
        """
        model_names = {mapper.class_.__name__ for mapper in Base.registry.mappers}
        unclassified: list[str] = []
        for repository in _all_repositories():
            if not is_tenant_scoped(_model_of(repository)):
                continue
            unclassified.extend(_unclassified(repository, model_names))

        assert sorted(unclassified) == sorted(EXPLICIT_EXCEPTIONS)

    def test_every_report_query_takes_a_hospital(self) -> None:
        """Reports aggregate across rows, so every public query must be scoped."""
        model_names = {mapper.class_.__name__ for mapper in Base.registry.mappers}
        assert _unclassified(ReportRepository, model_names) == []

    def test_every_exception_has_a_reason(self) -> None:
        assert all(reason.strip() for reason in EXPLICIT_EXCEPTIONS.values())

    @pytest.mark.parametrize(
        "primitive", ["get_by_id", "get_by_ids", "list", "update_by_pk", "count", "exists"]
    )
    def test_base_primitives_accept_a_scope(self, primitive: str) -> None:
        parameters = inspect.signature(getattr(BaseRepository, primitive)).parameters
        assert "scope" in parameters
        assert parameters["scope"].default is None
