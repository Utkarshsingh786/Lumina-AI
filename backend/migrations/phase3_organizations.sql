-- Phase 3: Team / Organisation multi-tenancy
-- Run: docker compose exec backend psql $DATABASE_URL -f migrations/phase3_organizations.sql

CREATE TABLE IF NOT EXISTS organizations (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name        VARCHAR(100)  NOT NULL,
    description TEXT,
    invite_token       VARCHAR(64) UNIQUE,
    invite_expires_at  TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_organizations_name         ON organizations (name);
CREATE INDEX IF NOT EXISTS ix_organizations_invite_token ON organizations (invite_token)
    WHERE invite_token IS NOT NULL;

CREATE TABLE IF NOT EXISTS organization_members (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organization_id  UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users(id)         ON DELETE CASCADE,
    role             VARCHAR(20) NOT NULL DEFAULT 'member',
    joined_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (organization_id, user_id)
);

CREATE INDEX IF NOT EXISTS ix_org_members_org  ON organization_members (organization_id);
CREATE INDEX IF NOT EXISTS ix_org_members_user ON organization_members (user_id);

-- Trigger to keep organizations.updated_at current
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_trigger WHERE tgname = 'trg_organizations_updated_at'
  ) THEN
    CREATE TRIGGER trg_organizations_updated_at
    BEFORE UPDATE ON organizations
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
  END IF;
END $$;
