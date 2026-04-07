"""Memory router — user-facing CRUD for their stored memory entries."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import LuminaError
from app.db.session import get_db
from app.models.user import User
from app.repositories.memory_repo import MemoryRepository
from app.schemas.common import PaginatedResponse, SuccessResponse
from app.schemas.memory import MemoryEntryResponse, MemoryToggleRequest

router = APIRouter(prefix="/memory", tags=["memory"])


class MemoryNotFoundError(LuminaError):
    def __init__(self) -> None:
        super().__init__(
            status_code=404,
            error_code="MEMORY_NOT_FOUND",
            message="Memory entry not found",
        )


@router.get("", response_model=PaginatedResponse[MemoryEntryResponse])
async def list_memories(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    memory_type: str | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[MemoryEntryResponse]:
    repo = MemoryRepository(db)
    offset = (page - 1) * page_size
    entries = await repo.get_user_memories(
        current_user.id,
        offset=offset,
        limit=page_size,
        memory_type=memory_type,
        include_inactive=include_inactive,
    )
    total = await repo.count_user_memories(current_user.id, include_inactive=include_inactive)
    return PaginatedResponse(
        items=[MemoryEntryResponse.model_validate(e) for e in entries],
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + page_size < total,
        has_prev=page > 1,
    )


@router.patch("/{memory_id}", response_model=MemoryEntryResponse)
async def toggle_memory(
    memory_id: UUID,
    data: MemoryToggleRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MemoryEntryResponse:
    repo = MemoryRepository(db)
    entry = await repo.get_user_memory(memory_id, current_user.id)
    if not entry:
        raise MemoryNotFoundError()
    updated = await repo.update(entry, is_active=data.is_active)
    return MemoryEntryResponse.model_validate(updated)


@router.delete("/{memory_id}", response_model=SuccessResponse)
async def delete_memory(
    memory_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SuccessResponse:
    repo = MemoryRepository(db)
    entry = await repo.get_user_memory(memory_id, current_user.id)
    if not entry:
        raise MemoryNotFoundError()
    await repo.delete(entry)
    return SuccessResponse(message="Memory deleted")
