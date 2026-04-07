"""
Generic base repository with common CRUD operations.

Why repository pattern:
- Decouples business logic from SQLAlchemy specifics
- Makes services testable (swap real repo for mock)
- Single place to add query optimization, caching hooks
- Keeps service code clean and readable

Design: typed generic over the model type (T).
Concrete repos inherit and add domain-specific query methods.
"""

from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """
    Type-safe async repository.
    Subclasses only need to define `model` class attribute.
    """

    model: type[ModelT]

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_id(self, id: UUID) -> ModelT | None:
        result = await self.db.execute(select(self.model).where(self.model.id == id))  # type: ignore[attr-defined]
        return result.scalar_one_or_none()

    async def get_all(
        self,
        offset: int = 0,
        limit: int = 50,
        filters: list[Any] | None = None,
    ) -> list[ModelT]:
        stmt = select(self.model)
        if filters:
            stmt = stmt.where(*filters)
        stmt = stmt.offset(offset).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count(self, filters: list[Any] | None = None) -> int:
        stmt = select(func.count()).select_from(self.model)
        if filters:
            stmt = stmt.where(*filters)
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def create(self, **kwargs: Any) -> ModelT:
        instance = self.model(**kwargs)
        self.db.add(instance)
        await self.db.flush()  # flush to get DB-generated values (id, timestamps)
        await self.db.refresh(instance)
        return instance

    async def update(self, instance: ModelT, **kwargs: Any) -> ModelT:
        for key, value in kwargs.items():
            setattr(instance, key, value)
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance

    async def delete(self, instance: ModelT) -> None:
        await self.db.delete(instance)
        await self.db.flush()

    async def save(self, instance: ModelT) -> ModelT:
        self.db.add(instance)
        await self.db.flush()
        await self.db.refresh(instance)
        return instance
