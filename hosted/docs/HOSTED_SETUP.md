# Project 3 Hosted Foundation

## Scope of this milestone

This milestone creates the hosted foundation for the existing Python crypto anomaly pipeline. The React/TypeScript/Vite operations dashboard is designed to be deployed separately on Vercel. The Python FastAPI service is designed to run on Render. Supabase PostgreSQL is the durable system of record for pipeline runs and the future anomaly, narrative, alert, and delivery-audit tables.

**Automatic alert delivery is not live in this milestone.** The API exposes readiness indicators that explicitly report alert delivery as disabled until the idempotent alert layer is implemented in Module 5B.

## Architecture

```text
Vercel
  React + TypeScript + Vite operations dashboard
          |
          | HTTPS, read-only health/run APIs
          v
Render
  Python FastAPI service
  existing Python pipeline domain modules
  scheduled execution added in the next Module 5 milestone
          |
          | SSL PostgreSQL connection
          v
Supabase
  pipeline_runs
  crypto_prices
  quality_flags
  anomalies
  narratives
  future alerts
  future delivery_attempts
```

The pipeline domain logic remains Python. It is not rewritten in Node.js. The JavaScript/TypeScript code is limited to the dashboard shell and the existing hosted-project scaffolding.

## Current API contract

| Endpoint | Purpose | Alert delivery status |
|---|---|---|
| `GET /health` | Service health and safe configuration indicators | Reports delivery disabled |
| `GET /api/readiness` | Hosted foundation readiness | Reports delivery disabled until Module 5B |
| `POST /api/pipeline-runs` | Start and persist one pipeline-run lifecycle | Does not send alerts |
| `PATCH /api/pipeline-runs/{run_id}` | Complete or update a lifecycle record | Does not send alerts |
| `GET /api/pipeline-runs?limit=20` | Inspect recent run history | Does not send alerts |
| `POST /api/alerts` | Create or retrieve one idempotent alert intent | Persists `pending`; delivery remains disabled |
| `GET /api/alerts?limit=20` | Inspect persisted alert intents | Does not deliver alerts |

The lifecycle contract records a UUID run id, UTC timestamps, status, stage counts, per-stage timings, and a sanitized error summary. Error summaries remove likely credentials, authorization values, bearer tokens, passwords, secrets, and URLs before persistence or response.

## Supabase setup

1. Create a Supabase project and open the project’s **Connect** panel.
2. Use the PostgreSQL connection string appropriate for the Render service. Supabase documents direct connections for long-lived backends and pooler session mode for IPv4-only persistent application traffic. Keep SSL enabled.
3. Run `python_service/sql/001_initial.sql` in the Supabase SQL editor or through the project’s migration process.
4. Confirm that `pipeline_runs` exists before connecting Render.
5. Use the database password only in Render’s secret environment settings; never commit it to Git or place it in the Vercel project.

The schema uses UTC `timestamptz` values, UUID run ids, JSONB stage timing maps, and unique keys that prepare the future alert layer for idempotent behavior.

## Render setup

Create a Python web service from the repository. Use the `python_service` directory as the service root if configuring a monorepo service.

| Render setting | Value |
|---|---|
| Runtime | Python 3 |
| Root directory | `python_service` |
| Build command | `pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

Configure these server-side environment variables in Render:

```text
SUPABASE_DATABASE_URL
GROQ_API_KEY
OPENROUTER_API_KEY
NARRATIVE_MODEL
OPENROUTER_MODEL
DASHBOARD_ORIGINS
ALERT_WEBHOOK_URL       # reserve for Module 5B; do not enable yet
ALERT_DELIVERY_ENABLED  # keep false until Module 5B
```

The API currently treats alert delivery as disabled regardless of future webhook configuration. This is intentional and prevents the dashboard from claiming that alerts are live before the delivery adapter is implemented. Module 5A.2 now adds idempotent alert-intent persistence: the key `anomaly_id:alert_type:channel` is unique, repeated requests return the existing alert, and every newly created alert remains in `pending` state without delivery.

Render’s start command must bind Uvicorn to `$PORT`; do not hard-code a port. The Python service should be deployed before the Vercel dashboard is pointed at it.

## Vercel setup

Import the React/Vite dashboard as a separate Vercel project. Configure:

```text
VITE_API_BASE_URL=https://<your-render-service>.onrender.com
```

Only variables prefixed with `VITE_` are available to the browser. Never use a `VITE_` prefix for Groq, OpenRouter, Supabase database, or webhook secrets. The dashboard only needs the public FastAPI base URL. It must never receive provider keys or the Supabase connection string.

For a Vite SPA, configure a rewrite to `index.html` if deep links such as `/runs` are used. The dashboard currently renders the same operations shell for the foundation routes and does not expose secret values.

## Deployment order

1. Apply the Supabase schema.
2. Deploy the Render FastAPI service.
3. Open Render’s `/health` and `/api/readiness` endpoints and confirm database configuration and alert-delivery-disabled status.
4. Configure `DASHBOARD_ORIGINS` in Render with the Vercel origin.
5. Set `VITE_API_BASE_URL` in Vercel.
6. Deploy the Vercel dashboard.
7. Open the dashboard and confirm the health, readiness, and recent-run views.
8. Use `POST /api/pipeline-runs` and `PATCH /api/pipeline-runs/{run_id}` to verify one lifecycle record.
9. Confirm that no alert is sent and that the UI still says alert delivery is disabled.
10. Only after Module 5B implements delivery attempts, retry policy, and a live channel should notification delivery be enabled. The Module 5A.2 alert endpoint may be tested in persistence-only mode.

## Safe verification examples

Start a lifecycle record:

```bash
curl -X POST "$RENDER_API_URL/api/pipeline-runs" \
  -H "Content-Type: application/json" \
  -d '{"status":"running","readings_fetched":5,"readings_inserted":5}'
```

Complete it using the returned `run_id`:

```bash
curl -X PATCH "$RENDER_API_URL/api/pipeline-runs/<RUN_ID>" \
  -H "Content-Type: application/json" \
  -d '{"status":"succeeded","readings_fetched":5,"readings_inserted":5,"quality_flags_count":0,"anomalies_count":0,"narratives_count":0,"stage_timings_ms":{"ingestion":751.5,"quality":13.2,"anomaly":21.9}}'
```

Inspect readiness:

```bash
curl "$RENDER_API_URL/api/readiness"
```

The readiness response should contain:

```json
{
  "automatic_alert_delivery": "disabled_until_module_5b_pending"
}
```

## Failure and security notes

The hosted API returns safe error summaries rather than raw exceptions containing credentials or complete URLs. The dashboard treats API failure as a visible connection state instead of fabricating run data. No sample customer reviews, ratings, or testimonials are included.

The external hosting choice is intentional because this project requires a Python backend and the requested Render/Vercel/Supabase separation. The current Manus project is used as the development and review workspace; the production deployment remains an independently configured Render service and Vercel frontend.

## References

1. [Supabase — Connect to your database](https://supabase.com/docs/guides/database/connecting-to-postgres)
2. [Render — Deploy a FastAPI App](https://render.com/docs/deploy-fastapi)
3. [Vercel — Vite on Vercel](https://vercel.com/docs/frameworks/frontend/vite)
