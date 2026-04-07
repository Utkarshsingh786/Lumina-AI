"""
Background task: parse + chunk + embed a document for RAG retrieval.

Pipeline:
  1. Load Document record, set status → indexing
  2. Read file bytes from storage
  3. Parse text (PDF / plain text / markdown)
  4. Chunk text into overlapping token windows
  5. Generate embeddings in batches (optional — skipped if no provider configured)
  6. Persist DocumentChunk rows + set embeddings via raw SQL
  7. Set Document.status → ready, chunk_count = N
  On any error: set status → error, save error_message

Why Celery:
- Embedding 100+ chunks via OpenAI API can take 5-30 s
- Must not block the HTTP upload response
- Retryable on transient API/DB failures

Why NullPool + fresh event loop per task:
- Celery uses prefork concurrency; forked processes inherit the parent's file
  descriptors and Python state, but asyncio event loops are NOT fork-safe.
- asyncpg connections are bound to the loop they were created on; reusing them
  in a new asyncio.run() call inside a forked worker raises:
    "Future attached to a different loop"
- Solution: each task creates its own event loop AND its own DB engine with
  NullPool (no connection pooling), so every session gets a fresh connection
  that is tied exclusively to the current event loop.
"""

import asyncio

from app.workers.celery_app import celery_app
from app.core.logging import get_logger

logger = get_logger(__name__)

# Number of texts per embeddings API call
_EMBED_BATCH_SIZE = 100


@celery_app.task(
    name="document_indexing.index_document",
    bind=True,
    max_retries=3,
    default_retry_delay=30,
)
def index_document_task(self, document_id: str) -> None:  # noqa: ARG002
    """Celery entry-point: runs the async pipeline in a clean event loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_async_index_document(document_id))
    finally:
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()


async def _async_index_document(document_id: str) -> None:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
    from sqlalchemy.pool import NullPool

    from app.ai.providers.router import TaskType, get_provider_for_task
    from app.ai.rag.chunker import TextChunker, parse_file_content
    from app.core.config import settings
    from app.models.document import (
        DOCUMENT_STATUS_ERROR,
        DOCUMENT_STATUS_INDEXING,
        DOCUMENT_STATUS_READY,
    )
    from app.repositories.document_repo import DocumentChunkRepository, DocumentRepository
    from app.services.document_service import DocumentService

    doc_uuid = UUID(document_id)

    # NullPool: each session creates/closes its own connection — no pool state
    # that could be tied to a prior event loop.
    celery_engine = create_async_engine(settings.DATABASE_URL, poolclass=NullPool)
    CelerySession = async_sessionmaker(
        bind=celery_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )

    try:
        async with CelerySession() as db:
            doc_repo = DocumentRepository(db)
            chunk_repo = DocumentChunkRepository(db)

            doc = await doc_repo.get_by_id(doc_uuid)
            if not doc:
                logger.error("document_indexing.doc_not_found", document_id=document_id)
                return

            # Mark as indexing
            await doc_repo.update(doc, status=DOCUMENT_STATUS_INDEXING)
            await db.commit()

            try:
                # 1. Read file
                file_path = DocumentService.get_absolute_path(doc.storage_path)
                file_bytes = file_path.read_bytes()

                # 2. Parse text
                text = parse_file_content(file_bytes, doc.file_type)
                if not text.strip():
                    await doc_repo.update(doc, status=DOCUMENT_STATUS_ERROR, error_message="No text content found")
                    await db.commit()
                    return

                # 3. Chunk text
                chunker = TextChunker(target_tokens=512, overlap_tokens=64)
                chunks = chunker.chunk(text)
                if not chunks:
                    await doc_repo.update(doc, status=DOCUMENT_STATUS_ERROR, error_message="Could not extract chunks")
                    await db.commit()
                    return

                logger.info(
                    "document_indexing.chunks_created",
                    document_id=document_id,
                    chunk_count=len(chunks),
                )

                # 4. Persist chunk rows (no embedding yet)
                chunk_dicts = [
                    {
                        "document_id": doc_uuid,
                        "user_id": doc.user_id,
                        "chunk_index": c.chunk_index,
                        "content": c.content,
                        "token_count": c.token_count,
                        "extra_metadata": c.metadata,
                    }
                    for c in chunks
                ]
                saved_chunks = await chunk_repo.bulk_create(chunk_dicts)
                await db.commit()

                # 5. Generate embeddings (optional — skipped if no provider configured)
                try:
                    provider, embed_model = get_provider_for_task(TaskType.EMBEDDING)
                    all_embeddings: list[list[float]] = []

                    for batch_start in range(0, len(chunks), _EMBED_BATCH_SIZE):
                        batch_texts = [c.content for c in chunks[batch_start : batch_start + _EMBED_BATCH_SIZE]]
                        batch_embeddings = await provider.generate_embeddings(
                            texts=batch_texts,
                            model=embed_model,
                        )
                        all_embeddings.extend(batch_embeddings)

                    # 6. Write embeddings via raw SQL
                    for saved_chunk, embedding in zip(saved_chunks, all_embeddings):
                        await chunk_repo.set_embedding(saved_chunk.id, embedding)
                    await db.commit()

                    logger.info(
                        "document_indexing.embeddings_stored",
                        document_id=document_id,
                        chunk_count=len(chunks),
                    )
                except Exception as embed_err:
                    # No embedding provider (no OpenAI/Gemini key) or quota exceeded.
                    # Document is still indexed as plain text — vector search won't
                    # work for this doc, but it won't block the user.
                    logger.warning(
                        "document_indexing.embeddings_skipped",
                        document_id=document_id,
                        reason=str(embed_err),
                    )

                # 7. Mark ready
                await doc_repo.update(doc, status=DOCUMENT_STATUS_READY, chunk_count=len(chunks))
                await db.commit()

                logger.info(
                    "document_indexing.complete",
                    document_id=document_id,
                    chunk_count=len(chunks),
                )

            except Exception as e:
                logger.error("document_indexing.error", document_id=document_id, error=str(e))
                try:
                    await doc_repo.update(
                        doc,
                        status=DOCUMENT_STATUS_ERROR,
                        error_message=str(e)[:500],
                    )
                    await db.commit()
                except Exception:
                    pass
    finally:
        await celery_engine.dispose()
