"""
RAG retriever — fetches relevant document chunks for context injection.

Strategy (in priority order):
  1. Vector similarity search  — requires embedding provider (OpenAI / Gemini)
  2. Full-text search (FTS)    — PostgreSQL tsvector, no API key needed
  3. All-chunks fallback       — inject first N chunks when FTS finds nothing

This means RAG works even without an embedding provider, giving every user
document context regardless of which AI keys are configured.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.repositories.document_repo import DocumentRepository

logger = get_logger(__name__)

_TOP_K = 5          # chunks to retrieve
_MIN_SCORE = 0.50   # minimum cosine similarity (vector path only)
_ALL_CHUNKS_LIMIT = 10  # max chunks for the all-chunks fallback


async def get_rag_context(
    db: AsyncSession,
    user_id: UUID,
    conversation_id: UUID,
    query: str,
) -> str | None:
    """
    Build a context string from documents attached to the conversation.

    Returns a formatted string ready to inject into the system prompt,
    or None if no documents exist. Never raises — errors are logged and
    swallowed so RAG failure never breaks the chat response.
    """
    doc_repo = DocumentRepository(db)

    # Fast exit: no ready documents → skip all retrieval work
    has_docs = await doc_repo.conversation_has_ready_documents(conversation_id, user_id)
    if not has_docs:
        return None

    # ── Path 1: Vector similarity search ──────────────────────────────────────
    try:
        query_embedding = await _embed_query(query)
        chunks = await doc_repo.search_similar_chunks(
            query_embedding=query_embedding,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=_TOP_K,
            min_score=_MIN_SCORE,
        )
        if chunks:
            logger.debug(
                "rag.vector_search_hit",
                count=len(chunks),
                conversation_id=str(conversation_id),
            )
            return _format_context(chunks)
        # Embedding succeeded but nothing above threshold — fall through to FTS
    except Exception as e:
        logger.debug(
            "rag.vector_search_unavailable",
            reason=str(e),
            conversation_id=str(conversation_id),
        )

    # ── Path 2: Full-text keyword search (no embedding provider needed) ────────
    try:
        chunks = await doc_repo.search_chunks_by_text(
            query=query,
            user_id=user_id,
            conversation_id=conversation_id,
            limit=_TOP_K,
        )
        if chunks:
            logger.debug(
                "rag.text_search_hit",
                count=len(chunks),
                conversation_id=str(conversation_id),
            )
            return _format_context(chunks)
    except Exception as e:
        logger.warning("rag.text_search_error", error=str(e), conversation_id=str(conversation_id))

    # ── Path 3: All-chunks fallback ────────────────────────────────────────────
    # FTS found nothing (query terms too short/generic) — inject first N chunks
    # so the model at least knows the document exists and can reason over it.
    try:
        chunks = await doc_repo.get_all_chunks_for_conversation(
            user_id=user_id,
            conversation_id=conversation_id,
            limit=_ALL_CHUNKS_LIMIT,
        )
        if chunks:
            logger.debug(
                "rag.all_chunks_fallback",
                count=len(chunks),
                conversation_id=str(conversation_id),
            )
            return _format_context(chunks)
    except Exception as e:
        logger.warning("rag.fallback_error", error=str(e), conversation_id=str(conversation_id))

    return None


async def _embed_query(query: str) -> list[float]:
    """Generate a single embedding for the user's query."""
    from app.ai.providers.router import TaskType, get_provider_for_task

    provider, embed_model = get_provider_for_task(TaskType.EMBEDDING)
    embeddings = await provider.generate_embeddings(texts=[query], model=embed_model)
    return embeddings[0]


def _format_context(chunks: list[dict]) -> str:
    """
    Format retrieved chunks into the string injected into the system prompt.

        [filename.pdf, excerpt 2]
        <content>

        [notes.txt, excerpt 1]
        <content>
    """
    parts: list[str] = []
    for chunk in chunks:
        header = f"[{chunk['filename']}, excerpt {chunk['chunk_index'] + 1}]"
        parts.append(f"{header}\n{chunk['content']}")
    return "\n\n".join(parts)
