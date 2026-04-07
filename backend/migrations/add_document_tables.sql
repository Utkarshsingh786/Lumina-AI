-- RAG: Document tables migration
-- Run once against your PostgreSQL database:
--   psql $DATABASE_URL -f backend/migrations/add_document_tables.sql

-- Enable pgvector extension (requires pgvector to be installed in PostgreSQL)
CREATE EXTENSION IF NOT EXISTS vector;

-- ── Documents ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    filename        TEXT NOT NULL,
    file_type       TEXT NOT NULL,
    file_size       INTEGER NOT NULL,
    storage_path    TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',   -- pending|indexing|ready|error
    chunk_count     INTEGER NOT NULL DEFAULT 0,
    error_message   TEXT,
    metadata        JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS documents_user_id_idx        ON documents(user_id);
CREATE INDEX IF NOT EXISTS documents_conversation_id_idx ON documents(conversation_id);
CREATE INDEX IF NOT EXISTS documents_status_idx          ON documents(status);

-- ── Document chunks ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS document_chunks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    chunk_index  INTEGER NOT NULL,
    content      TEXT NOT NULL,
    token_count  INTEGER NOT NULL DEFAULT 0,
    embedding    vector(1536),   -- text-embedding-3-small output dimension
    metadata     JSONB NOT NULL DEFAULT '{}',
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS document_chunks_document_id_idx ON document_chunks(document_id);
CREATE INDEX IF NOT EXISTS document_chunks_user_id_idx     ON document_chunks(user_id);

-- IVFFlat index for approximate nearest-neighbour search (cosine distance).
-- lists=100 is a sensible default for up to ~1M vectors; tune as data grows.
-- This index only helps once there are >1000 rows; ignored below that threshold.
CREATE INDEX IF NOT EXISTS document_chunks_embedding_idx
    ON document_chunks
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);
