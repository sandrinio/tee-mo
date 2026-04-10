-- =============================================================================
-- Migration: 001_teemo_users
-- Purpose:   Create the teemo_users table — account holders for Tee-Mo dashboard.
-- Safe to run multiple times (idempotent via IF NOT EXISTS).
-- =============================================================================

-- Enable pgcrypto for gen_random_uuid() (Supabase usually has it, but be explicit).
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- -----------------------------------------------------------------------------
-- Shared updated_at trigger function (used by several teemo_ tables).
-- Safe to create or replace; one shared function serves all teemo_ tables.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION teemo_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- -----------------------------------------------------------------------------
-- teemo_users
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS teemo_users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(320) NOT NULL UNIQUE,  -- RFC 5321 max length
    password_hash   VARCHAR(255) NOT NULL,         -- bcrypt output
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Index for login lookups (email is already UNIQUE, which creates an index,
-- but a case-insensitive index speeds up case-insensitive login.)
CREATE INDEX IF NOT EXISTS idx_teemo_users_email_lower
    ON teemo_users (LOWER(email));

-- updated_at trigger
DROP TRIGGER IF EXISTS trg_teemo_users_updated_at ON teemo_users;
CREATE TRIGGER trg_teemo_users_updated_at
    BEFORE UPDATE ON teemo_users
    FOR EACH ROW
    EXECUTE FUNCTION teemo_set_updated_at();

-- -----------------------------------------------------------------------------
-- Row Level Security
-- Tee-Mo uses custom JWT auth, so RLS is disabled — all access goes through
-- the FastAPI backend using the service_role key. The backend enforces
-- per-user isolation via explicit WHERE clauses (Charter §2.4 Security First).
-- -----------------------------------------------------------------------------
ALTER TABLE teemo_users DISABLE ROW LEVEL SECURITY;

-- -----------------------------------------------------------------------------
-- Sanity check: print row count (0 on first run)
-- -----------------------------------------------------------------------------
DO $$
DECLARE
    cnt BIGINT;
BEGIN
    SELECT COUNT(*) INTO cnt FROM teemo_users;
    RAISE NOTICE '✓ teemo_users migration complete. Current row count: %', cnt;
END $$;
