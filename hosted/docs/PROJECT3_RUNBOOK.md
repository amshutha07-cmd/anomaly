# Project 3 — Hosted Crypto Anomaly Monitor Runbook

**Purpose.** This runbook explains what Project 3 contains, how the pieces fit together, how to reproduce the work later, and how to continue from Module 5A.1. It is written as an operational handoff rather than a one-time implementation note.

## 1. Project outcome

Project 3 is a crypto-market anomaly monitoring platform. The original Python pipeline fetches BTC, ETH, and USDT data, stores readings, runs quality checks, detects anomalies, generates an AI-assisted explanation, and records the result. The hosted foundation adds a separate FastAPI service and a React/Vite operations dashboard so the system can eventually run independently of a local computer.

The Python domain logic remains Python. The React/TypeScript/Vite application is the operations interface. The intended production boundary is:

| Layer | Technology | Responsibility |
|---|---|---|
| Dashboard | React, TypeScript, Vite | Display health, readiness, run history, and future alert state. |
| API service | Python FastAPI on Render | Expose safe lifecycle and health APIs; host the existing Python pipeline domain logic. |
| Durable database | Supabase PostgreSQL | Store pipeline runs, crypto readings, quality flags, anomalies, narratives, alerts, and delivery attempts. |
| Scheduling | Render scheduled execution | Run the Python pipeline independently of the developer’s laptop after the alert foundation is ready. |
| Narrative providers | Groq primary, OpenRouter fallback | Explain validated anomalies; never decide alert escalation. |

Automatic alert delivery is intentionally disabled in Module 5A.1. The dashboard must not describe alerts as live until the idempotent alert layer and delivery adapter are implemented and tested.

## 2. Completed local pipeline baseline

Modules 1–4 were verified before hosted work began.

| Module | What it does | Important evidence |
|---|---|---|
| Module 1 | CoinGecko primary ingestion with Binance coverage/failover for BTC, ETH, and USDT. | A live run fetched 5 readings and inserted 5 records. |
| Module 2 | Quality checks, schema/sanity checks, polling-gap detection, and quality flag persistence. | Runs correctly recorded gap flags when polling was delayed. |
| Module 3 | Return-based z-score/IQR checks and USDT peg-deviation checks. | Controlled runs produced statistical/IQR anomalies and evaluated the USDT peg threshold. |
| Module 4 | Type-specific LLM narratives with strict validation and provider metadata. | Groq primary succeeded; forced Groq failure switched to OpenRouter `stealth/ox-alpha`, returned HTTP 200, and persisted a validated narrative. |

The Module 4 provider design is Groq primary with OpenRouter fallback. No Anthropic key is required. The fallback was tested with a temporary invalid Groq key inside a process; the real key was not changed.

## 3. Hosted Module 5A.1 foundation

Module 5A.1 establishes the lifecycle contract before scheduled execution and live alerting are enabled.

The Python service is under `python_service/`. Its main responsibilities are health reporting, readiness reporting, starting a pipeline run, updating a pipeline run, listing recent runs, and sanitizing error summaries. It does not expose provider credentials and it does not send automatic alerts.

The SQL file `python_service/sql/001_initial.sql` defines the Supabase-ready tables and future alert/delivery structures. The `pipeline_runs` table is designed around a UUID `run_id`, UTC `timestamptz` values, status, stage counts, per-stage timing JSON, and a safe error summary. The future `alerts` design uses an idempotency key so a repeated run cannot create duplicate alert intent.

The Render blueprint is `render.yaml`. It sets the Python service root to `python_service`, uses `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, points health checks at `/health`, and keeps credentials as unsynchronized secret fields. `ALERT_DELIVERY_ENABLED` is explicitly set to `false`.

The React dashboard is under `client/`. `DashboardLayout.tsx` provides the sidebar frame. `Home.tsx` provides the operations shell and route-aware content for Overview, Run history, Alert readiness, and Configuration. `VITE_API_BASE_URL` is the only dashboard-side connection setting; provider keys and the Supabase connection string must remain server-side.

## 4. Important files and what to edit

| File | Edit it when you need to… |
|---|---|
| `python_service/app/main.py` | Change FastAPI endpoints, lifecycle validation, safe error handling, or readiness output. |
| `python_service/sql/001_initial.sql` | Change the Supabase schema for new installations. Apply migrations separately for an existing database. |
| `python_service/requirements.txt` | Add Python service dependencies. |
| `python_service/tests/test_main.py` | Add Python contract tests for service behavior. |
| `render.yaml` | Change Render service settings or server-side environment variable declarations. |
| `client/src/pages/Home.tsx` | Change dashboard content, API reads, route-specific views, or readiness messaging. |
| `client/src/components/DashboardLayout.tsx` | Change navigation labels, sidebar structure, or application shell. |
| `client/src/index.css` | Change the visual system, spacing, colors, backgrounds, and status accents. |
| `client/src/App.tsx` | Register routes and global providers. |
| `server/hostedReadiness.ts` | Change the typed frontend-side readiness contract. |
| `server/hostedReadiness.test.ts` | Test that readiness does not expose secrets and alert delivery remains disabled. |
| `HOSTED_SETUP.md` | Maintain Supabase, Render, Vercel, environment, and deployment instructions. |
| `docs/module1-4-baseline.md` | Maintain the handoff from the verified local pipeline to the hosted foundation. |
| `todo.md` | Record every feature, bug, test, and delivery checkpoint. |

Do not edit framework files under `server/_core/` unless a documented infrastructure extension is required. Do not put API keys in React code, `VITE_` variables, screenshots, logs, SQL data, or documentation.

## 5. Environment variable boundary

### Render-only variables

| Variable | Purpose |
|---|---|
| `SUPABASE_DATABASE_URL` | Server-side PostgreSQL connection string with SSL enabled. |
| `GROQ_API_KEY` | Groq narrative provider credential. |
| `OPENROUTER_API_KEY` | OpenRouter fallback credential. |
| `NARRATIVE_MODEL` | Groq primary model, currently `openai/gpt-oss-120b`. |
| `OPENROUTER_MODEL` | OpenRouter fallback model, currently `stealth/ox-alpha`. |
| `DASHBOARD_ORIGINS` | Allowed Vercel origin(s) for FastAPI CORS. |
| `ALERT_WEBHOOK_URL` | Reserved for the future delivery adapter; do not enable in Module 5A.1. |
| `ALERT_DELIVERY_ENABLED` | Must remain `false` until the idempotent alert module is complete. |

### Vercel-side variable

```text
VITE_API_BASE_URL=https://<your-render-service>.onrender.com
```

Only the public API base URL belongs in the Vercel dashboard. Never prefix a secret with `VITE_`.

## 6. Reproducing local verification

From the hosted repository root:

```bash
pnpm check
pnpm test
pnpm build
python3 -m py_compile python_service/app/main.py python_service/tests/test_main.py
python3 -m unittest discover -s python_service/tests -p 'test_*.py'
```

The successful baseline currently includes three Vitest tests across two files and four Python service unit tests. The frontend build may show a bundle-size warning; that is a performance follow-up, not a build failure.

To inspect the dashboard preview, use the local development command from the project package scripts and open the generated preview URL. The dashboard intentionally displays an awaiting-connection state until `VITE_API_BASE_URL` points to a configured FastAPI service. That is a truthful readiness state, not fabricated demo data.

## 7. Supabase setup sequence

Create a Supabase project, open the database Connect panel, and select a PostgreSQL connection mode appropriate for the Render service. Keep SSL enabled. Apply `python_service/sql/001_initial.sql` in the Supabase SQL editor or through a controlled migration process. Verify that `pipeline_runs` exists before connecting Render.

Never commit the database password. Place the complete connection string only in Render’s server-side secret settings. If the schema changes later, create an explicit numbered migration and record the migration in the runbook.

## 8. Render setup sequence

Create a Python web service from the repository and set the root directory to `python_service`. Use the build command `pip install -r requirements.txt` and the start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. Set `/health` as the health check path. Add the server-side variables listed above.

After deployment, verify:

```bash
curl https://<your-render-service>.onrender.com/health
curl https://<your-render-service>.onrender.com/api/readiness
```

The readiness response must indicate that the pipeline-run lifecycle is available or awaiting configuration and that automatic alert delivery is disabled. Do not schedule the full pipeline until the hosted lifecycle and database connection have been verified.

## 9. Vercel setup sequence

Import the React/Vite dashboard as a separate Vercel project. Use the repository’s frontend build configuration and set `VITE_API_BASE_URL` to the Render service URL. Add the SPA rewrite from `vercel.json` so `/runs`, `/alerts`, and `/settings` remain reachable on direct navigation.

After deployment, open the dashboard and confirm that it shows the FastAPI health state, readiness state, current run history, and the explicit alert-disabled message. If the dashboard says “Awaiting connection,” inspect the Vercel API base URL, Render CORS origin, and the Render health endpoint before changing application code.

## 10. Module 5A.2 continuation plan

The next implementation stage is the idempotent alert foundation. It should add an `alerts` table with a unique idempotency key, a deterministic severity-to-alert policy, a delivery adapter interface, delivery-attempt records, retry classification, and a dry-run mode. Alert creation should be persisted only after the anomaly and narrative are durable. Delivery should remain disabled until duplicate suppression and failure behavior are tested.

The preferred progression is:

| Stage | Completion gate |
|---|---|
| Alert schema | Existing anomaly and narrative rows can map to one unique alert intent. |
| Idempotency | Repeating the same input creates zero additional alert intents. |
| Dry-run delivery | Payload is rendered and logged safely without sending. |
| Webhook adapter | HTTP success, timeout, 429, 4xx, and 5xx behavior are tested. |
| Scheduler | A hosted run executes without the local computer. |
| Operational UI | Alert status, attempts, failures, and suppression counts are visible. |

## 11. Troubleshooting guide

| Symptom | Likely cause | Response |
|---|---|---|
| Dashboard says awaiting connection | `VITE_API_BASE_URL` is missing or FastAPI is not reachable. | Test Render `/health` directly, then verify the Vercel variable and CORS origin. |
| FastAPI starts but database is unavailable | Invalid Supabase connection string, SSL mode, or missing Render secret. | Check the server-side variable and Supabase connection mode; do not print the credential. |
| CORS failure in browser | Vercel origin is absent from `DASHBOARD_ORIGINS`. | Add the exact deployed origin server-side and redeploy. |
| Alert delivery appears live too early | A UI label or environment flag was changed prematurely. | Restore `ALERT_DELIVERY_ENABLED=false` and the explicit Module 5A.1 readiness message. |
| Duplicate alert appears | Idempotency key is incomplete or uniqueness is not enforced. | Include anomaly identity, alert type, and channel in a unique key and add a rerun test. |
| Raw credential appears in logs | Error sanitization missed a provider-specific pattern. | Add a regression test for the pattern and redact before persistence/logging. |

## 12. Interview and resume framing

The project should be described as a **fault-tolerant, idempotent crypto anomaly monitoring platform with AI-assisted explanations and an auditable hosted operations layer**. Emphasize that anomaly decisions remain deterministic, the LLM is used for explanation, provider fallback is explicit, credentials are server-side, and alerts are designed around idempotent persistence rather than blind notification calls.

The strongest Module 5 metrics to capture are successful hosted runs, end-to-end latency, anomalies detected, narratives generated, alerts created, duplicate alerts suppressed, delivery retries, failed deliveries, fallback-provider usage, and p95 delivery latency.

## References

1. [Supabase — Connect to your database](https://supabase.com/docs/guides/database/connecting-to-postgres)
2. [Render — Deploy a FastAPI App](https://render.com/docs/deploy-fastapi)
3. [Vercel — Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite)

## 13. Module 5A.2 alert foundation completed

Module 5A.2 now provides idempotent alert-intent persistence without enabling live delivery. The FastAPI service exposes `POST /api/alerts` and `GET /api/alerts`. The POST contract accepts an anomaly identity, optional narrative and run identifiers, alert type, severity, and channel. The service derives the unique key `anomaly_id:alert_type:channel`, inserts a pending alert when the key is new, and returns the existing alert when the same request is repeated.

The alert state is deliberately `pending`. The response includes `delivery_enabled=false` and the message that delivery remains disabled until the later delivery module. The `dry_run_delivery()` helper renders the delivery boundary without performing network I/O, allowing payload and policy behavior to be tested safely before a real webhook is configured.

The alert schema already includes `alerts` and `delivery_attempts` tables. The current implementation does not send webhooks, email, or other notifications. That boundary is intentional: persistence and idempotency are tested before external side effects are introduced.

The verification suite now covers secret-safe error summaries, run defaults and validation, deterministic idempotency keys, invalid severity rejection, delivery-disabled responses, dry-run non-delivery, repository duplicate suppression, and direct FastAPI duplicate-request suppression. The Python suite completed with 10 passing tests. The frontend TypeScript check, Vitest suite, and production build also pass.

The next step is Module 5A.3/5B delivery engineering: add delivery-attempt records, retry classification, a test webhook adapter, and explicit enablement controls. Do not set `ALERT_DELIVERY_ENABLED=true` until those pieces and their failure-mode tests are complete.
