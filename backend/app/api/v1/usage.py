"""
Usage & cost analytics endpoints.

Endpoints:
  GET /usage/summary   — aggregate totals for the current user (optional date range)
  GET /usage/timeline  — daily breakdown (tokens + cost) for the last N days
  GET /usage/by-model  — per-model breakdown

Data source: ai_generations table — every LLM call is logged there with
  provider, model, prompt_tokens, completion_tokens, total_tokens, cost_usd,
  latency_ms, created_at.
"""

from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.conversation import Conversation
from app.models.message import AIGeneration
from app.models.user import User

router = APIRouter(prefix="/usage", tags=["usage"])


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _date_bounds(days: int) -> tuple[datetime, datetime]:
    end = _utc_now()
    start = end - timedelta(days=days)
    return start, end


@router.get("/summary")
async def usage_summary(
    days: int = Query(default=30, ge=1, le=365, description="Look-back window in days"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Aggregate token usage and cost for the current user over the last N days.

    Returns:
      total_tokens, total_prompt_tokens, total_completion_tokens,
      total_cost_usd, total_requests, avg_latency_ms,
      period_start, period_end
    """
    start, end = _date_bounds(days)

    # Sub-select: all conversation IDs belonging to this user
    user_conv_ids = select(Conversation.id).where(Conversation.user_id == current_user.id)

    result = await db.execute(
        select(
            func.coalesce(func.sum(AIGeneration.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AIGeneration.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(AIGeneration.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(AIGeneration.cost_usd), 0).label("total_cost_usd"),
            func.count(AIGeneration.id).label("total_requests"),
            func.coalesce(func.avg(AIGeneration.latency_ms), 0).label("avg_latency_ms"),
        )
        .where(AIGeneration.conversation_id.in_(user_conv_ids))
        .where(AIGeneration.created_at >= start)
        .where(AIGeneration.created_at <= end)
        .where(AIGeneration.error.is_(None))
    )
    row = result.one()

    return {
        "total_tokens": int(row.total_tokens),
        "total_prompt_tokens": int(row.prompt_tokens),
        "total_completion_tokens": int(row.completion_tokens),
        "total_cost_usd": float(row.total_cost_usd or 0),
        "total_requests": int(row.total_requests),
        "avg_latency_ms": int(row.avg_latency_ms or 0),
        "period_days": days,
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
    }


@router.get("/timeline")
async def usage_timeline(
    days: int = Query(default=30, ge=1, le=365, description="Number of days to show"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Daily usage breakdown for the last N days.

    Returns a list of {date, tokens, cost_usd, requests} objects sorted ascending.
    Days with zero activity are included so the chart has a continuous x-axis.
    """
    start, end = _date_bounds(days)
    user_conv_ids = select(Conversation.id).where(Conversation.user_id == current_user.id)

    day_trunc = func.date_trunc(text("'day'"), AIGeneration.created_at)

    result = await db.execute(
        select(
            day_trunc.label("day"),
            func.coalesce(func.sum(AIGeneration.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(AIGeneration.cost_usd), 0).label("cost_usd"),
            func.count(AIGeneration.id).label("requests"),
        )
        .where(AIGeneration.conversation_id.in_(user_conv_ids))
        .where(AIGeneration.created_at >= start)
        .where(AIGeneration.created_at <= end)
        .where(AIGeneration.error.is_(None))
        .group_by(day_trunc)
        .order_by(day_trunc)
    )
    rows = result.all()

    # Build a dict keyed by date string for O(1) lookup
    data_by_date: dict[str, dict] = {}
    for row in rows:
        day_str = row.day.strftime("%Y-%m-%d") if row.day else ""
        data_by_date[day_str] = {
            "date": day_str,
            "tokens": int(row.tokens),
            "cost_usd": float(row.cost_usd or 0),
            "requests": int(row.requests),
        }

    # Fill in zero-days so the frontend chart has a continuous range.
    # Use range(days + 1) to include today (end date).
    timeline = []
    for i in range(days + 1):
        d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
        timeline.append(
            data_by_date.get(d, {"date": d, "tokens": 0, "cost_usd": 0.0, "requests": 0})
        )

    return {"timeline": timeline, "period_days": days}


@router.get("/by-model")
async def usage_by_model(
    days: int = Query(default=30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Per-model token and cost breakdown for the last N days.
    Sorted by total_tokens descending.
    """
    start, _ = _date_bounds(days)
    user_conv_ids = select(Conversation.id).where(Conversation.user_id == current_user.id)

    result = await db.execute(
        select(
            AIGeneration.model,
            AIGeneration.provider,
            func.coalesce(func.sum(AIGeneration.total_tokens), 0).label("total_tokens"),
            func.coalesce(func.sum(AIGeneration.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(AIGeneration.completion_tokens), 0).label("completion_tokens"),
            func.coalesce(func.sum(AIGeneration.cost_usd), 0).label("total_cost_usd"),
            func.count(AIGeneration.id).label("requests"),
            func.coalesce(func.avg(AIGeneration.latency_ms), 0).label("avg_latency_ms"),
        )
        .where(AIGeneration.conversation_id.in_(user_conv_ids))
        .where(AIGeneration.created_at >= start)
        .where(AIGeneration.error.is_(None))
        .group_by(AIGeneration.model, AIGeneration.provider)
        .order_by(func.sum(AIGeneration.total_tokens).desc())
    )
    rows = result.all()

    return {
        "models": [
            {
                "model": r.model,
                "provider": r.provider,
                "total_tokens": int(r.total_tokens),
                "prompt_tokens": int(r.prompt_tokens),
                "completion_tokens": int(r.completion_tokens),
                "total_cost_usd": float(r.total_cost_usd or 0),
                "requests": int(r.requests),
                "avg_latency_ms": int(r.avg_latency_ms or 0),
            }
            for r in rows
        ],
        "period_days": days,
    }
