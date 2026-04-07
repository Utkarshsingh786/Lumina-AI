"""Conversation and message repositories."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.conversation import Conversation
from app.models.message import AIGeneration, Message, MessageFeedback
from app.repositories.base import BaseRepository


class ConversationRepository(BaseRepository[Conversation]):
    model = Conversation

    async def get_user_conversations(
        self,
        user_id: UUID,
        offset: int = 0,
        limit: int = 50,
        include_archived: bool = False,
    ) -> list[Conversation]:
        """
        Paginated list for sidebar — ordered by last activity.
        Pinned conversations float to top.
        """
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.is_archived == include_archived)
            .order_by(
                desc(Conversation.is_pinned),
                desc(Conversation.last_message_at),
                desc(Conversation.created_at),
            )
            .offset(offset)
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_with_messages(self, conversation_id: UUID, user_id: UUID) -> Conversation | None:
        """Eager-load messages to avoid N+1 in detail view."""
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.id == conversation_id)
            .where(Conversation.user_id == user_id)
            .options(selectinload(Conversation.messages))
        )
        return result.scalar_one_or_none()

    async def count_user_conversations(
        self, user_id: UUID, include_archived: bool = False
    ) -> int:
        result = await self.db.execute(
            select(func.count(Conversation.id))
            .where(Conversation.user_id == user_id)
            .where(Conversation.is_archived == include_archived)
        )
        return result.scalar_one()

    async def touch_last_message(self, conversation_id: UUID) -> None:
        """Update last_message_at and increment message_count atomically."""
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(
                last_message_at=datetime.now(timezone.utc),
                message_count=Conversation.message_count + 1,
            )
        )

    async def update_token_count(self, conversation_id: UUID, tokens: int) -> None:
        await self.db.execute(
            update(Conversation)
            .where(Conversation.id == conversation_id)
            .values(token_count=Conversation.token_count + tokens)
        )

    async def search(self, user_id: UUID, query: str, limit: int = 20) -> list[Conversation]:
        """Full-text search on conversation titles."""
        stmt = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .where(Conversation.title.ilike(f"%{query}%"))
            .order_by(desc(Conversation.last_message_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())


class MessageRepository(BaseRepository[Message]):
    model = Message

    async def get_conversation_messages(
        self,
        conversation_id: UUID,
        limit: int = 100,
        offset: int = 0,
        exclude_deleted: bool = True,
    ) -> list[Message]:
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at)
            .offset(offset)
            .limit(limit)
        )
        if exclude_deleted:
            stmt = stmt.where(Message.is_deleted.is_(False))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_recent_messages(
        self, conversation_id: UUID, limit: int = 50
    ) -> list[Message]:
        """Get most recent N messages — used for context building."""
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .where(Message.is_deleted.is_(False))
            .where(Message.role != "system")
            .order_by(desc(Message.created_at))
            .limit(limit)
        )
        result = await self.db.execute(stmt)
        # Return in chronological order for context building
        return list(reversed(result.scalars().all()))

    async def count_conversation_messages(self, conversation_id: UUID) -> int:
        result = await self.db.execute(
            select(func.count(Message.id))
            .where(Message.conversation_id == conversation_id)
            .where(Message.is_deleted.is_(False))
        )
        return result.scalar_one()

    async def create_ai_generation(self, **kwargs) -> AIGeneration:
        gen = AIGeneration(**kwargs)
        self.db.add(gen)
        await self.db.flush()
        return gen

    async def upsert_feedback(
        self, message_id: UUID, user_id: UUID, rating: int, comment: str | None
    ) -> MessageFeedback:
        # Check if feedback already exists
        result = await self.db.execute(
            select(MessageFeedback)
            .where(MessageFeedback.message_id == message_id)
            .where(MessageFeedback.user_id == user_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing.rating = rating
            existing.comment = comment
            await self.db.flush()
            return existing
        feedback = MessageFeedback(
            message_id=message_id, user_id=user_id, rating=rating, comment=comment
        )
        self.db.add(feedback)
        await self.db.flush()
        return feedback
