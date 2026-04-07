-- Agent workflow run history
-- Run: docker compose exec backend psql $DATABASE_URL -f migrations/agent_workflow_runs.sql

CREATE TABLE IF NOT EXISTS workflow_runs (
    id              UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID        NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    workflow_id     VARCHAR(100) NOT NULL,
    workflow_name   VARCHAR(200) NOT NULL,
    workflow_icon   VARCHAR(10)  NOT NULL DEFAULT '⚡',
    input           TEXT         NOT NULL,
    model           VARCHAR(200) NOT NULL,
    status          VARCHAR(20)  NOT NULL DEFAULT 'running',
    step_results    JSONB        NOT NULL DEFAULT '[]',
    total_tokens    INTEGER      NOT NULL DEFAULT 0,
    error           TEXT,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_workflow_runs_user_id     ON workflow_runs (user_id);
CREATE INDEX IF NOT EXISTS ix_workflow_runs_workflow_id ON workflow_runs (workflow_id);
CREATE INDEX IF NOT EXISTS ix_workflow_runs_status      ON workflow_runs (status);
CREATE INDEX IF NOT EXISTS ix_workflow_runs_created_at  ON workflow_runs (created_at DESC);
