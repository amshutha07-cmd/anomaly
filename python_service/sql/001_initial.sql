-- Project 3 hosted foundation schema.
-- Run with a Supabase migration workflow. All timestamps are UTC timestamptz.

create extension if not exists pgcrypto;

create table if not exists pipeline_runs (
  run_id uuid primary key default gen_random_uuid(),
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  status text not null check (status in ('running', 'succeeded', 'failed', 'partial')),
  readings_fetched integer not null default 0 check (readings_fetched >= 0),
  readings_inserted integer not null default 0 check (readings_inserted >= 0),
  quality_flags_count integer not null default 0 check (quality_flags_count >= 0),
  anomalies_count integer not null default 0 check (anomalies_count >= 0),
  narratives_count integer not null default 0 check (narratives_count >= 0),
  alerts_created integer not null default 0 check (alerts_created >= 0),
  alerts_sent integer not null default 0 check (alerts_sent >= 0),
  alerts_failed integer not null default 0 check (alerts_failed >= 0),
  stage_timings_ms jsonb not null default '{}'::jsonb,
  error_summary text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists pipeline_runs_started_at_idx on pipeline_runs (started_at desc);
create index if not exists pipeline_runs_status_idx on pipeline_runs (status);

create table if not exists crypto_prices (
  id bigserial primary key,
  run_id uuid references pipeline_runs(run_id) on delete set null,
  recorded_at timestamptz not null,
  asset_id text not null,
  source text not null,
  price_usd numeric(30, 12) not null,
  volume_24h numeric(30, 12),
  raw_payload jsonb,
  created_at timestamptz not null default now(),
  unique (recorded_at, asset_id, source)
);

create index if not exists crypto_prices_asset_time_idx
  on crypto_prices (asset_id, recorded_at desc);

create table if not exists quality_flags (
  id bigserial primary key,
  run_id uuid references pipeline_runs(run_id) on delete set null,
  recorded_at timestamptz not null,
  asset_id text,
  source text,
  flag_type text not null,
  severity text not null check (severity in ('info', 'warning', 'error')),
  detail text not null,
  created_at timestamptz not null default now()
);

create index if not exists quality_flags_run_idx on quality_flags (run_id);

create table if not exists anomalies (
  id bigserial primary key,
  run_id uuid references pipeline_runs(run_id) on delete set null,
  recorded_at timestamptz not null,
  asset_id text not null,
  anomaly_type text not null,
  observed_value numeric(30, 12),
  reference_value numeric(30, 12),
  score numeric(30, 12),
  threshold_used numeric(30, 12),
  detail text not null,
  created_at timestamptz not null default now()
);

create index if not exists anomalies_time_idx on anomalies (recorded_at desc);
create index if not exists anomalies_run_idx on anomalies (run_id);

create table if not exists narratives (
  anomaly_id bigint primary key references anomalies(id) on delete cascade,
  severity text not null check (severity in ('low', 'medium', 'high')),
  likely_cause text not null,
  recommended_action text not null,
  narrative text not null,
  provider_used text not null,
  model_used text not null,
  latency_ms numeric(14, 3),
  prompt_tokens integer,
  completion_tokens integer,
  fallback_used boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists alerts (
  alert_id uuid primary key default gen_random_uuid(),
  anomaly_id bigint not null references anomalies(id) on delete cascade,
  narrative_id bigint references narratives(anomaly_id) on delete set null,
  run_id uuid references pipeline_runs(run_id) on delete set null,
  alert_type text not null,
  severity text not null check (severity in ('low', 'medium', 'high')),
  channel text not null,
  idempotency_key text not null unique,
  status text not null check (status in ('pending', 'sending', 'sent', 'failed', 'acknowledged', 'resolved')),
  attempt_count integer not null default 0 check (attempt_count >= 0),
  last_error text,
  created_at timestamptz not null default now(),
  sent_at timestamptz,
  acknowledged_at timestamptz,
  resolved_at timestamptz
);

create index if not exists alerts_status_idx on alerts (status, created_at desc);
create index if not exists alerts_anomaly_idx on alerts (anomaly_id);

create table if not exists delivery_attempts (
  attempt_id uuid primary key default gen_random_uuid(),
  alert_id uuid not null references alerts(alert_id) on delete cascade,
  attempt_number integer not null check (attempt_number > 0),
  channel text not null,
  status text not null check (status in ('started', 'succeeded', 'failed')),
  http_status integer,
  provider_message_id text,
  error_message text,
  started_at timestamptz not null default now(),
  completed_at timestamptz,
  unique (alert_id, attempt_number)
);

create index if not exists delivery_attempts_alert_idx on delivery_attempts (alert_id, started_at desc);
