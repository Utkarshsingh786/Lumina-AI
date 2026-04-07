"""Repository for Document and DocumentChunk CRUD + vector similarity search."""

from uuid import UUID

from sqlalchemy import desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import Document, DocumentChunk, DOCUMENT_STATUS_READY
from app.repositories.base import BaseRepository


class DocumentRepository(BaseRepository[Document]):
    model = Document

    async def get_conversation_documents(
        self,
        conversation_id: UUID,
        user_id: UUID,
    ) -> list[Document]:
        result = await self.db.execute(
            select(Document)
            .where(Document.conversation_id == conversation_id)
            .where(Document.user_id == user_id)
            .order_by(desc(Document.created_at))
        )
        return list(result.scalars().all())

    async def get_user_document(self, document_id: UUID, user_id: UUID) -> Document | None:
        result = await self.db.execute(
            select(Document)
            .where(Document.id == document_id)
            .where(Document.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def conversation_has_ready_documents(
        self, conversation_id: UUID, user_id: UUID
    ) -> bool:
        result = await self.db.execute(
            select(Document.id)
            .where(Document.conversation_id == conversation_id)
            .where(Document.user_id == user_id)
            .where(Document.status == DOCUMENT_STATUS_READY)
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def get_all_chunks_for_conversation(
        self,
        user_id: UUID,
        conversation_id: UUID,
        limit: int = 20,
    ) -> list[dict]:
        """
        Return up to `limit` chunks from all ready documents in a conversation.
        Used as a last-resort fallback when no embedding provider is configured.
        """
        stmt = text("""
            SELECT
                dc.content,
                dc.chunk_index,
                d.filename,
                1.0 AS score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.user_id = :user_id
              AND d.conversation_id = :conversation_id
              AND d.status = 'ready'
            ORDER BY d.created_at DESC, dc.chunk_index ASC
            LIMIT :limit
        """)
        result = await self.db.execute(
            stmt,
            {"user_id": str(user_id), "conversation_id": str(conversation_id), "limit": limit},
        )
        rows = result.fetchall()
        return [
            {"content": row.content, "chunk_index": row.chunk_index, "filename": row.filename, "score": 1.0}
            for row in rows
        ]

    async def search_chunks_by_text(
        self,
        query: str,
        user_id: UUID,
        conversation_id: UUID,
        limit: int = 5,
    ) -> list[dict]:
        """
        PostgreSQL full-text search over chunk content.
        Fallback for when no embedding provider is configured.
        Uses ts_rank so results are ordered by keyword relevance.
        """
        stmt = text("""
            SELECT
                dc.content,
                dc.chunk_index,
                d.filename,
                ts_rank(
                    to_tsvector('english', dc.content),
                    plainto_tsquery('english', :query)
                ) AS score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.user_id    = :user_id
              AND d.conversation_id = :conversation_id
              AND d.status = 'ready'
              AND to_tsvector('english', dc.content) @@ plainto_tsquery('english', :query)
            ORDER BY score DESC
            LIMIT :limit
        """)
        result = await self.db.execute(
            stmt,
            {
                "query": query,
                "user_id": str(user_id),
                "conversation_id": str(conversation_id),
                "limit": limit,
            },
        )
        rows = result.fetchall()
        return [
            {"content": row.content, "chunk_index": row.chunk_index, "filename": row.filename, "score": float(row.score)}
            for row in rows
        ]

    async def search_similar_chunks(
        self,
        query_embedding: list[float],
        user_id: UUID,
        conversation_id: UUID,
        limit: int = 5,
        min_score: float = 0.5,
    ) -> list[dict]:
        """
        Cosine similarity search over document_chunks for a given user + conversation.

        Uses pgvector's <=> operator (cosine distance). Score = 1 - distance,
        so higher score = more similar.

        Returns list of dicts with keys: content, filename, chunk_index, score.
        """
        embedding_str = "[" + ",".join(str(v) for v in query_embedding) + "]"

        stmt = text("""
            SELECT
                dc.content,
                dc.chunk_index,
                d.filename,
                1 - (dc.embedding <=> :embedding::vector) AS score
            FROM document_chunks dc
            JOIN documents d ON d.id = dc.document_id
            WHERE dc.user_id = :user_id
              AND d.conversation_id = :conversation_id
              AND d.status = 'ready'
              AND dc.embedding IS NOT NULL
              AND 1 - (dc.embedding <=> :embedding::vector) >= :min_score
            ORDER BY dc.embedding <=> :embedding::vector
            LIMIT :limit
        """)

        result = await self.db.execute(
            stmt,
            {
                "embedding": embedding_str,
                "user_id": str(user_id),
                "conversation_id": str(conversation_id),
                "min_score": min_score,
                "limit": limit,
            },
        )
        rows = result.fetchall()
        return [
            {
                "content": row.content,
                "chunk_index": row.chunk_index,
                "filename": row.filename,
                "score": float(row.score),
            }
            for row in rows
        ]


class DocumentChunkRepository(BaseRepository[DocumentChunk]):
    model = DocumentChunk

    async def bulk_create(self, chunks: list[dict]) -> list[DocumentChunk]:
        """Insert multiple chunks in one flush (no embeddings yet)."""
        objects = [DocumentChunk(**c) for c in chunks]
        for obj in objects:
            self.db.add(obj)
        await self.db.flush()
        for obj in objects:
            await self.db.refresh(obj)
        return objects

    async def set_embedding(self, chunk_id: UUID, embedding: list[float]) -> None:
        """Update a single chunk's embedding via raw SQL (pgvector)."""
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        stmt = text("""
            UPDATE document_chunks
            SET embedding = :embedding::vector
            WHERE id = :chunk_id
        """)
        await self.db.execute(stmt, {"embedding": embedding_str, "chunk_id": str(chunk_id)})
