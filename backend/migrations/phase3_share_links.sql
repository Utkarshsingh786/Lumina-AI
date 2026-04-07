-- Phase 3: Share conversation links
-- Run: docker compose exec backend psql $DATABASE_URL -f migrations/phase3_share_links.sql

ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS share_token VARCHAR(64) UNIQUE,
  ADD COLUMN IF NOT EXISTS is_public   BOOLEAN NOT NULL DEFAULT FALSE;

CREATE INDEX IF NOT EXISTS ix_conversations_share_token
  ON conversations (share_token)
  WHERE share_token IS NOT NULL;
