-- ============================================================
-- 012_teemo_automations.sql
-- Automation tables, SQL functions, and triggers for Tee-Mo
--
-- Purpose:
--   Creates the persistence layer for scheduled AI automations (EPIC-018).
--   Provides CRUD tables, a next-run-time calculator, a due-automations query,
--   and BEFORE INSERT/UPDATE triggers that automatically set next_run_at.
--
-- ADR References:
--   ADR-015: All DB access via Supabase service-role key (no RLS needed)
--   ADR-020: Self-hosted Supabase — RLS DISABLED, ownership enforced at app layer
--   ADR-024: Workspace model — workspace_id present on every teemo_* table
--
-- Depends on:
--   002_teemo_workspaces.sql  — teemo_workspaces table (workspace_id FK)
--   006_teemo_workspace_channels.sql — teemo_workspace_channels table (channel validation)
-- ============================================================

-- 1. teemo_automations — scheduled AI task definitions
CREATE TABLE IF NOT EXISTS teemo_automations (
    id                  UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id        UUID        NOT NULL REFERENCES teemo_workspaces(id) ON DELETE CASCADE,
    name                TEXT        NOT NULL,
    description         TEXT,
    prompt              TEXT        NOT NULL,
    slack_channel_ids   TEXT[]      NOT NULL,
    schedule            JSONB       NOT NULL,
    schedule_type       TEXT        NOT NULL DEFAULT 'recurring' CHECK (schedule_type IN ('recurring', 'once')),
    timezone            TEXT        NOT NULL DEFAULT 'UTC',
    is_active           BOOLEAN     DEFAULT TRUE,
    owner_user_id       UUID        NOT NULL REFERENCES teemo_users(id),
    last_run_at         TIMESTAMPTZ,
    next_run_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ DEFAULT now(),
    updated_at          TIMESTAMPTZ DEFAULT now(),
    UNIQUE (workspace_id, name),
    CONSTRAINT check_slack_channel_ids_nonempty CHECK (array_length(slack_channel_ids, 1) >= 1)
);

COMMENT ON TABLE teemo_automations IS 'Scheduled AI tasks. Prompt may contain @[Doc] mentions resolved at execution time.';

-- 2. teemo_automation_executions — execution history
CREATE TABLE IF NOT EXISTS teemo_automation_executions (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    automation_id     UUID        NOT NULL REFERENCES teemo_automations(id) ON DELETE CASCADE,
    status            TEXT        NOT NULL DEFAULT 'pending',
    started_at        TIMESTAMPTZ DEFAULT now(),
    completed_at      TIMESTAMPTZ,
    generated_content TEXT,
    delivery_results  JSONB,
    was_dry_run       BOOLEAN     DEFAULT FALSE,
    error             TEXT,
    tokens_used       INT,
    execution_time_ms INT,
    CONSTRAINT check_execution_status CHECK (status IN ('pending', 'running', 'success', 'partial', 'failed'))
);

COMMENT ON TABLE teemo_automation_executions IS 'Execution history for automations. Capped at 50 rows per automation by service layer.';

-- 3. Indexes
CREATE INDEX IF NOT EXISTS idx_teemo_automations_due
    ON teemo_automations (is_active, next_run_at)
    WHERE is_active = TRUE;

CREATE INDEX IF NOT EXISTS idx_teemo_automations_workspace
    ON teemo_automations (workspace_id);

CREATE INDEX IF NOT EXISTS idx_teemo_automation_executions_automation
    ON teemo_automation_executions (automation_id, started_at DESC);

-- 4. calculate_next_run_time — timezone-correct next run calculator
--
-- Copied verbatim from new_app/database/migrations/034_fix_once_schedule_timezone.sql
-- lines 14-152. This is the IMMUTABLE version that correctly interprets `once` schedule
-- timestamps in the user's timezone (not the server timezone). Do NOT use the 025 version.
CREATE OR REPLACE FUNCTION calculate_next_run_time(
    schedule JSONB,
    from_time TIMESTAMPTZ DEFAULT NOW()
) RETURNS TIMESTAMPTZ AS $$
DECLARE
    sched JSONB;
    occurrence TEXT;
    when_time TEXT;
    timezone_name TEXT;
    days_array INTEGER[];
    day_of_month INTEGER;
    once_at TEXT;
    next_run TIMESTAMPTZ;
    base_time TIMESTAMP;
    current_dow INTEGER;
    target_dow INTEGER;
    days_ahead INTEGER;
    found_day BOOLEAN;
    i INTEGER;
BEGIN
    -- If schedule is a JSON string (e.g. doubly-encoded via PostgREST when the
    -- caller sends json.dumps() output), unwrap it to a JSON object first.
    IF jsonb_typeof(schedule) = 'string' THEN
        sched := (schedule #>> '{}')::JSONB;
    ELSE
        sched := schedule;
    END IF;

    occurrence := sched->>'occurrence';
    when_time := sched->>'when';
    timezone_name := COALESCE(sched->>'timezone', 'UTC');

    -- Handle one-time schedule
    IF occurrence = 'once' THEN
        once_at := sched->>'at';
        IF once_at IS NULL THEN
            RETURN NULL;
        END IF;
        -- Interpret the timestamp in the user's timezone, then convert to UTC.
        -- This ensures 11:40 PM Asia/Tbilisi → 19:40 UTC regardless of server tz.
        next_run := (once_at::TIMESTAMP AT TIME ZONE timezone_name);
        IF next_run <= from_time THEN
            RETURN NULL;
        END IF;
        RETURN next_run;
    END IF;

    -- Parse days array for weekly
    IF sched ? 'days' THEN
        SELECT ARRAY(
            SELECT jsonb_array_elements_text(sched->'days')::INTEGER
            ORDER BY 1
        ) INTO days_array;
    END IF;

    -- Parse day_of_month for monthly
    IF sched ? 'day_of_month' THEN
        day_of_month := (sched->>'day_of_month')::INTEGER;
    END IF;

    -- Convert from_time to target timezone
    base_time := from_time AT TIME ZONE timezone_name;

    -- Calculate next run: today at specified time in target timezone
    next_run := (base_time::DATE + when_time::TIME) AT TIME ZONE timezone_name;

    -- If the time has passed today, start from tomorrow
    IF next_run <= from_time THEN
        next_run := next_run + INTERVAL '1 day';
    END IF;

    CASE occurrence
        WHEN 'daily' THEN
            -- Already calculated above
            NULL;

        WHEN 'weekdays' THEN
            -- Skip weekends: Saturday=6, Sunday=0
            WHILE EXTRACT(DOW FROM next_run AT TIME ZONE timezone_name) IN (0, 6) LOOP
                next_run := next_run + INTERVAL '1 day';
            END LOOP;

        WHEN 'weekly' THEN
            IF days_array IS NULL OR array_length(days_array, 1) IS NULL THEN
                RETURN NULL;
            END IF;

            found_day := FALSE;
            FOR i IN 1..14 LOOP
                current_dow := EXTRACT(DOW FROM next_run AT TIME ZONE timezone_name)::INTEGER;
                IF current_dow = ANY(days_array) THEN
                    found_day := TRUE;
                    EXIT;
                END IF;
                next_run := next_run + INTERVAL '1 day';
            END LOOP;

            IF NOT found_day THEN
                RETURN NULL;
            END IF;

        WHEN 'monthly' THEN
            IF day_of_month IS NULL THEN
                RETURN NULL;
            END IF;

            -- Start from current month, find the next valid day_of_month
            DECLARE
                candidate_date DATE;
                month_offset INTEGER := 0;
            BEGIN
                FOR month_offset IN 0..12 LOOP
                    candidate_date := (
                        DATE_TRUNC('month', (next_run AT TIME ZONE timezone_name)::DATE)
                        + (month_offset || ' months')::INTERVAL
                        + ((day_of_month - 1) || ' days')::INTERVAL
                    )::DATE;

                    -- Skip if the day doesn't exist in this month (e.g. Feb 30)
                    IF EXTRACT(DAY FROM candidate_date) != day_of_month THEN
                        CONTINUE;
                    END IF;

                    next_run := (candidate_date + when_time::TIME) AT TIME ZONE timezone_name;

                    IF next_run > from_time THEN
                        RETURN next_run;
                    END IF;
                END LOOP;
                RETURN NULL;
            END;

        ELSE
            RETURN NULL;
    END CASE;

    RETURN next_run;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- 5. get_due_automations — returns active automations ready to execute
CREATE OR REPLACE FUNCTION get_due_automations()
RETURNS SETOF teemo_automations AS $$
    SELECT * FROM teemo_automations
    WHERE is_active = TRUE
      AND next_run_at IS NOT NULL
      AND next_run_at <= NOW()
    ORDER BY next_run_at ASC;
$$ LANGUAGE sql STABLE;

-- 6. Triggers for next_run_at management

-- INSERT trigger: set initial next_run_at
-- Uses COALESCE(NEW.is_active, TRUE) because PostgREST may not send is_active
-- in the payload (relying on the DEFAULT TRUE), which makes NEW.is_active NULL
-- in a BEFORE INSERT trigger before defaults are applied. Treating NULL as TRUE
-- ensures the trigger correctly sets next_run_at for new active automations.
CREATE OR REPLACE FUNCTION trigger_set_teemo_automation_next_run() RETURNS TRIGGER AS $$
BEGIN
    IF COALESCE(NEW.is_active, TRUE) AND NEW.next_run_at IS NULL THEN
        NEW.next_run_at := calculate_next_run_time(NEW.schedule, NOW());
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_teemo_automation_initial_next_run
    BEFORE INSERT ON teemo_automations
    FOR EACH ROW
    EXECUTE FUNCTION trigger_set_teemo_automation_next_run();

-- UPDATE trigger: recalculate next_run_at when schedule, is_active, or timezone changes
CREATE OR REPLACE FUNCTION trigger_update_teemo_automation_next_run() RETURNS TRIGGER AS $$
BEGIN
    IF (OLD.schedule IS DISTINCT FROM NEW.schedule)
       OR (OLD.is_active IS DISTINCT FROM NEW.is_active)
       OR (OLD.timezone IS DISTINCT FROM NEW.timezone) THEN
        IF NEW.is_active THEN
            NEW.next_run_at := calculate_next_run_time(NEW.schedule, COALESCE(NEW.last_run_at, NOW()));
        ELSE
            NEW.next_run_at := NULL;
        END IF;
    END IF;
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_teemo_automation_next_run
    BEFORE UPDATE ON teemo_automations
    FOR EACH ROW
    EXECUTE FUNCTION trigger_update_teemo_automation_next_run();

-- 7. Disable RLS — ownership enforced at application layer (ADR-020)
ALTER TABLE teemo_automations DISABLE ROW LEVEL SECURITY;
ALTER TABLE teemo_automation_executions DISABLE ROW LEVEL SECURITY;

DO $$ BEGIN
    RAISE NOTICE '✓ teemo_automations migration complete';
END $$;
