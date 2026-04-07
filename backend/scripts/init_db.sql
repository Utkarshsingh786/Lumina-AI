-- PostgreSQL initialization script
-- Runs once when the container is first created

-- Enable pgvector extension for semantic search / RAG
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Verify
SELECT extname, extversion FROM pg_extension WHERE extname IN ('vector', 'pgcrypto');
