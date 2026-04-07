"""Repository for MemoryEntry CRUD operations."""

from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.memory import MemoryEntry
from app.repositories.base import BaseRepository


class MemoryRepository(BaseRepository[MemoryEntry]):
    model = MemoryEntry

    async def get_user_memories(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 50,
        memory_type: str | None = None,
        include_inactive: bool = False,
    ) -> list[MemoryEntry]:
        stmt = (
            select(MemoryEntry)
            .where(MemoryEntry.user_id == user_id)
            .order_by(desc(MemoryEntry.importance), desc(MemoryEntry.created_at))
            .offset(offset)
            .limit(limit)
        )
        if memory_type:
            stmt = stmt.where(MemoryEntry.memory_type == memory_type)
        if not include_inactive:
            stmt = stmt.where(MemoryEntry.is_active.is_(True))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def count_user_memories(
        self,
        user_id: UUID,
        include_inactive: bool = False,
    ) -> int:
        from sqlalchemy import func
        stmt = select(func.count()).select_from(MemoryEntry).where(MemoryEntry.user_id == user_id)
        if not include_inactive:
            stmt = stmt.where(MemoryEntry.is_active.is_(True))
        result = await self.db.execute(stmt)
        return result.scalar_one()

    async def get_user_memory(self, memory_id: UUID, user_id: UUID) -> MemoryEntry | None:
        result = await self.db.execute(
            select(MemoryEntry)
            .where(MemoryEntry.id == memory_id)
            .where(MemoryEntry.user_id == user_id)
        )
        return result.scalar_one_or_none()
