"""Generic base repository providing common CRUD operations.

All business-module repositories inherit from :class:`BaseRepository`.
It provides type-safe, async CRUD with soft-delete and pagination support.

Repositories NEVER contain business logic. They only handle data access.
"""

from __future__ import annotations

import uuid  # noqa: TC003 — needed at runtime for type hints
from typing import TYPE_CHECKING, Any

from sqlalchemy import Select, UnaryExpression, func, select, update

from app.database.base_class import Base
from app.models.base import SoftDeleteMixin

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.sql import ColumnElement


class BaseRepository[ModelT: Base]:
    """Generic repository providing common database operations.

    :param model_class: The SQLAlchemy model class this repository manages.
    :param session: An async SQLAlchemy session.
    """

    def __init__(self, model_class: type[ModelT], session: AsyncSession) -> None:
        self._model = model_class
        self._session = session

    # ── Query Building ────────────────────────────────────────────────────────

    def _soft_delete_supported(self) -> bool:
        """Check if the model class supports soft delete."""
        return issubclass(self._model, SoftDeleteMixin)

    def _apply_soft_delete_filter(self, stmt: Select[tuple[ModelT]]) -> Select[tuple[ModelT]]:
        """Append ``WHERE deleted_at IS NULL`` if the model supports soft delete."""
        if self._soft_delete_supported():
            return stmt.where(self._model.deleted_at.is_(None))  # type: ignore[attr-defined]
        return stmt

    def _apply_pagination(
        self,
        stmt: Select[tuple[ModelT]],
        skip: int = 0,
        limit: int = 100,
    ) -> Select[tuple[ModelT]]:
        """Apply offset/limit pagination."""
        return stmt.offset(skip).limit(limit)

    def _apply_ordering(
        self,
        stmt: Select[tuple[ModelT]],
        *order_by: UnaryExpression[Any],
    ) -> Select[tuple[ModelT]]:
        """Apply column ordering."""
        if order_by:
            return stmt.order_by(*order_by)
        return stmt.order_by(self._model.created_at.desc())  # type: ignore[attr-defined]

    # ── Base Query ────────────────────────────────────────────────────────────

    def _query(self) -> Select[tuple[ModelT]]:
        """Return a base ``SELECT *`` statement with soft-delete filtering."""
        return self._apply_soft_delete_filter(select(self._model))

    # ── CRUD Operations ───────────────────────────────────────────────────────

    async def create(self, **kwargs: Any) -> ModelT:
        """Create a new record and flush to the database.

        :param kwargs: Column values for the new record.
        :returns: The created ORM instance.
        """
        instance = self._model(**kwargs)
        self._session.add(instance)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def get_by_id(self, id: uuid.UUID) -> ModelT | None:
        """Retrieve a record by its UUID primary key.

        :param id: The UUID of the record.
        :returns: The ORM instance, or ``None`` if not found or soft-deleted.
        """
        stmt = self._query().where(self._model.id == id)  # type: ignore[attr-defined]
        result = await self._session.execute(stmt)
        return result.unique().scalar_one_or_none()

    async def get_by_ids(self, ids: list[uuid.UUID]) -> list[ModelT]:
        """Retrieve multiple records by their UUID primary keys.

        :param ids: List of UUIDs.
        :returns: List of found ORM instances (excludes soft-deleted).
        """
        stmt = self._query().where(self._model.id.in_(ids))  # type: ignore[attr-defined]
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def list(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        order_by: ColumnElement[Any] | None = None,
    ) -> list[ModelT]:
        """List records with pagination.

        :param skip: Number of records to skip (offset).
        :param limit: Maximum number of records to return.
        :param order_by: Optional column expression for ordering.
        :returns: List of ORM instances.
        """
        stmt = self._query()
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        stmt = self._apply_pagination(stmt, skip=skip, limit=limit)
        result = await self._session.execute(stmt)
        return list(result.unique().scalars().all())

    async def update(self, instance: ModelT, **kwargs: Any) -> ModelT:
        """Update a record with the provided field values.

        The instance is modified in-place and flushed to the database.

        :param instance: The ORM instance to update (must be attached to session).
        :param kwargs: Field names and their new values.
        :returns: The updated ORM instance.
        """
        for field, value in kwargs.items():
            if hasattr(instance, field):
                setattr(instance, field, value)
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def update_by_pk(self, id: uuid.UUID, **kwargs: Any) -> ModelT | None:
        """Update a record identified by its primary key.

        :param id: The UUID of the record to update.
        :param kwargs: Field names and their new values.
        :returns: The updated ORM instance, or ``None``.
        """
        stmt = (
            update(self._model)
            .where(self._model.id == id)  # type: ignore[attr-defined]
            .values(**kwargs)
            .returning(self._model)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        row = result.unique().scalar_one_or_none()
        if row is not None:
            await self._session.refresh(row)
        return row

    async def soft_delete(self, instance: ModelT) -> ModelT:
        """Soft-delete a record (sets ``deleted_at``).

        :param instance: The ORM instance to soft-delete.
        :returns: The soft-deleted ORM instance.
        :raises TypeError: If the model does not support soft delete.
        """
        if not self._soft_delete_supported():
            msg = f"{self._model.__name__} does not support soft delete."
            raise TypeError(msg)
        instance.deleted_at = func.now()  # type: ignore[attr-defined]
        await self._session.flush()
        await self._session.refresh(instance)
        return instance

    async def hard_delete(self, instance: ModelT) -> None:
        """Permanently delete a record from the database.

        Use sparingly. Most business tables should use :meth:`soft_delete`.

        :param instance: The ORM instance to permanently delete.
        """
        await self._session.delete(instance)
        await self._session.flush()

    async def count(
        self,
        stmt: Select[tuple[ModelT]] | None = None,
    ) -> int:
        """Count records matching an optional filter.

        :param stmt: Optional select statement. Defaults to the base query.
        :returns: The record count.
        """
        query = self._apply_soft_delete_filter(stmt if stmt is not None else select(self._model))
        count_stmt = select(func.count()).select_from(query.subquery())
        result = await self._session.execute(count_stmt)
        return result.scalar_one()

    async def exists(self, id: uuid.UUID) -> bool:
        """Check if a record with the given ID exists (and is not soft-deleted).

        :param id: The UUID to check.
        :returns: ``True`` if the record exists.
        """
        if self._soft_delete_supported():
            stmt = select(func.count()).where(
                self._model.id == id,  # type: ignore[attr-defined]
                self._model.deleted_at.is_(None),  # type: ignore[attr-defined]
            )
        else:
            stmt = select(func.count()).where(self._model.id == id)  # type: ignore[attr-defined]
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0
