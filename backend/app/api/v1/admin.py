"""
Admin panel API — requires role == "admin".

Endpoints:
  GET   /admin/users              — paginated user list with usage stats
  PATCH /admin/users/{id}         — update role / active status
  GET   /admin/stats              — system-wide counts
  GET   /admin/usage              — global token / cost aggregation

Design notes:
- All endpoints require a valid JWT AND role == "admin".
- Stats are computed with aggregate SQL — no separate materialized view needed
  at this scale. Add caching (Redis) if counts become slow in production.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.document import Document
from app.models.message import AIGeneration, Message
from app.models.user import User
from app.repositories.user_repo import UserRepository
from app.schemas.auth import UserResponse
from app.schemas.common import PaginatedResponse, SuccessResponse

router = APIRouter(prefix="/admin", tags=["admin"])


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency: raises 403 unless caller has role == 'admin'."""
    if current_user.role != "admin":
        raise PermissionDeniedError("Admin access required")
    return current_user


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def list_users(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    search: str | None = Query(default=None, description="Filter by email or username"),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> PaginatedResponse[UserResponse]:
    """Paginated list of all users. Searchable by email/username."""
    from sqlalchemy import or_

    stmt = select(User).order_by(User.created_at.desc())
    if search:
        pattern = f"%{search}%"
        stmt = stmt.where(
            or_(User.email.ilike(pattern), User.username.ilike(pattern))
        )

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(stmt)
    users = result.scalars().all()

    return PaginatedResponse(
        items=[UserResponse.model_validate(u) for u in users],
        total=total,
        page=page,
        page_size=page_size,
        has_next=offset + page_size < total,
        has_prev=page > 1,
    )


@router.patch("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: UUID,
    body: dict,
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """
    Update a user's role or active status.

    Allowed fields: role (str), is_active (bool).
    Admins cannot demote themselves to prevent lockout.
    """
    repo = UserRepository(db)
    user = await repo.get_by_id(user_id)
    if not user:
        raise NotFoundError("User not found")

    # Prevent self-demotion
    if user.id == _admin.id and body.get("role") and body["role"] != "admin":
        raise PermissionDeniedError("Admins cannot remove their own admin role")

    allowed = {"role", "is_active"}
    update_kwargs = {k: v for k, v in body.items() if k in allowed}
    if not update_kwargs:
        raise PermissionDeniedError("No valid fields to update")

    updated = await repo.update(user, **update_kwargs)
    await db.commit()
    await db.refresh(updated)
    return UserResponse.model_validate(updated)


# ── System Stats ──────────────────────────────────────────────────────────────

@router.get("/stats")
async def system_stats(
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    System-wide aggregate counts.

    Returns total users, conversations, messages, documents, and 24h activity.
    """
    yesterday = datetime.now(timezone.utc) - timedelta(hours=24)

    results = await db.execute(
        select(
            func.count(User.id).label("total_users"),
            func.sum(cast(User.is_active, Integer)).label("active_users"),
        )
    )
    user_row = results.one()

    conv_result = await db.execute(select(func.count(Conversation.id)))
    total_conversations = conv_result.scalar_one()

    msg_result = await db.execute(
        select(func.count(Message.id)).where(Message.role == "user")
    )
    total_messages = msg_result.scalar_one()

    doc_result = await db.execute(select(func.count(Document.id)))
    total_documents = doc_result.scalar_one()

    new_users_24h = await db.execute(
        select(func.count(User.id)).where(User.created_at >= yesterday)
    )
    new_convs_24h = await db.execute(
        select(func.count(Conversation.id)).where(Conversation.created_at >= yesterday)
    )

    return {
        "users": {
            "total": int(user_row.total_users or 0),
            "active": int(user_row.active_users or 0),
            "new_24h": int(new_users_24h.scalar_one() or 0),
        },
        "conversations": {
            "total": int(total_conversations or 0),
            "new_24h": int(new_convs_24h.scalar_one() or 0),
        },
        "messages": {"total": int(total_messages or 0)},
        "documents": {"total": int(total_documents or 0)},
    }


@router.get("/usage")
async def global_usage(
    days: int = Query(default=30, ge=1, le=365),
    _admin: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Global token usage and cost for the last N days, broken down by provider/model.
    """
    start = datetime.now(timezone.utc) - timedelta(days=days)

    totals = await db.execute(
        select(
            func.coalesce(func.sum(AIGeneration.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AIGeneration.cost_usd), 0).label("total_cost_usd"),
            func.count(AIGeneration.id).label("total_requests"),
        )
        .where(AIGeneration.created_at >= start)
        .where(AIGeneration.error.is_(None))
    )
    totals_row = totals.one()

    by_provider = await db.execute(
        select(
            AIGeneration.provider,
            func.coalesce(func.sum(AIGeneration.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(AIGeneration.cost_usd), 0).label("cost_usd"),
            func.count(AIGeneration.id).label("requests"),
        )
        .where(AIGeneration.created_at >= start)
        .where(AIGeneration.error.is_(None))
        .group_by(AIGeneration.provider)
        .order_by(func.sum(AIGeneration.total_tokens).desc())
    )

    return {
        "total_tokens": int(totals_row.total_tokens),
        "total_cost_usd": float(totals_row.total_cost_usd or 0),
        "total_requests": int(totals_row.total_requests),
        "period_days": days,
        "by_provider": [
            {
                "provider": r.provider,
                "tokens": int(r.tokens),
                "cost_usd": float(r.cost_usd or 0),
                "requests": int(r.requests),
            }
            for r in by_provider.all()
        ],
    }
