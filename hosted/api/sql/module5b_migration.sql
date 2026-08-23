-- Module 5B: alert delivery state machine and attempt audit trail.
-- Run this once in Supabase SQL Editor before deploying the API changes.
CREATE EXTENSION IF NOT EXISTS pgcrypto;

ALTER TABLE alerts ADD COLUMN IF NOT EXISTS acknowledged_at timestamptz;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS next_attempt_at timestamptz;
ALTER TABLE alerts ADD COLUMN IF NOT EXISTS last_attempt_at timestamptz;

-- Replace any existing status check on alerts so the state machine is explicit.
DO $$
DECLARE c record;
BEGIN
  FOR c IN
    SELECT conname
    FROM pg_constraint
    WHERE conrelid = 'alerts'::regclass
      AND contype = 'c'
      AND pg_get_constraintdef(oid) ILIKE '%status%'
  LOOP
    EXECUTE format('ALTER TABLE alerts DROP CONSTRAINT %I', c.conname);
  END LOOP;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'alerts'::regclass
      AND conname = 'alerts_delivery_status_check'
  ) THEN
    ALTER TABLE alerts
      ADD CONSTRAINT alerts_delivery_status_check
      CHECK (status IN ('pending', 'sending', 'sent', 'acknowledged', 'failed'));
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS alerts_due_delivery_idx
  ON alerts (status, next_attempt_at, created_at);

CREATE TABLE IF NOT EXISTS alert_delivery_attempts (
  attempt_id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  alert_id uuid NOT NULL REFERENCES alerts(alert_id) ON DELETE CASCADE,
  attempt_number integer NOT NULL CHECK (attempt_number > 0),
  status text NOT NULL CHECK (status IN ('started', 'sent', 'failed', 'skipped')),
  provider text,
  response_code integer,
  error_summary text,
  started_at timestamptz NOT NULL DEFAULT now(),
  finished_at timestamptz,
  UNIQUE (alert_id, attempt_number)
);

CREATE INDEX IF NOT EXISTS alert_delivery_attempts_alert_idx
  ON alert_delivery_attempts (alert_id, started_at DESC);