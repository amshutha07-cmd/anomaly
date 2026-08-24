# Veyra

## Evidence-led digital-asset anomaly monitoring

Veyra is a hosted crypto anomaly-detection and alerting platform that turns digital-asset observations into explainable, auditable operational decisions.

The system follows a complete analytical lifecycle:

```
market observations
  → data-quality validation
  → deterministic anomaly detection
  → persisted detector evidence
  → conditional AI narrative
  → idempotent alert intent
  → controlled provider delivery
  → delivery-attempt audit
```

Veyra is designed as a portfolio-grade demonstration of how statistical analysis can be moved beyond a notebook into a reliable, authenticated, observable service. It is not a trading system, a price-prediction model, or a custody platform.

## Why the project exists

A notebook can identify an unusual data point. A production-oriented monitoring system must also answer what data was evaluated, whether the input was trustworthy, why the point was considered unusual, whether an explanation was generated, whether an alert should be sent, whether a provider accepted it, and what happened when delivery failed.

Veyra addresses that complete chain. The detector remains deterministic and interpretable. AI is used as an explanation layer after a finding exists. Alert creation is idempotent, delivery moves through explicit states, retries are bounded, and every provider attempt is retained for review.

## Current production demonstration

The live dashboard is available at:

[**https://anomaly-plum.vercel.app**](https://anomaly-plum.vercel.app)

The hosted API is available at:

[**https://anomaly-api-rnvm.onrender.com**](https://anomaly-api-rnvm.onrender.com)

The deployed demonstration includes authenticated dashboard access, protected FastAPI data routes, Supabase PostgreSQL persistence, live Slack webhook delivery, GitHub Actions scheduling, and a real delivery audit.

The verified evidence set includes 21 persisted anomaly findings, 6 persisted narratives, 2 alert intents, and 4 delivery-attempt records. The latest monitoring cycle can legitimately show zero new anomalies while those historical records remain available for investigation.

## Architecture

| Layer | Technology | Responsibility |
| --- | --- | --- |
| Detection pipeline | Python | Ingest observations, validate quality, run deterministic detectors, and persist local results |
| Hosted API | FastAPI and `asyncpg` | Authenticate requests, expose readiness and evidence routes, manage alert intents, and dispatch eligible alerts |
| Database | Supabase PostgreSQL | Store pipeline runs, readings, quality flags, anomalies, narratives, alerts, and delivery attempts |
| Dashboard | React, Vite, TypeScript, Tailwind | Present current operational state and historical analytical evidence |
| Authentication | Supabase Auth | Provide authenticated analyst sessions and access tokens |
| AI explanation | Groq with OpenRouter fallback | Generate structured analyst-readable narratives after detector findings exist |
| Alert provider | Slack-compatible webhook | Receive controlled alert notifications |
| Hosting | Vercel and Render | Host the frontend and API independently with explicit environment boundaries |
| Automation | GitHub Actions | Run bounded monitoring cycles and synchronize results |

### Frontend-to-backend flow

```
Browser loads Vercel dashboard
        ↓
User signs in through Supabase Auth
        ↓
Frontend receives an access token
        ↓
apiFetch attaches Authorization: Bearer <token>
        ↓
FastAPI middleware validates the token
        ↓
FastAPI queries Supabase PostgreSQL server-side
        ↓
JSON evidence returns to the dashboard
        ↓
React renders current state and historical records
```

The browser never receives the database connection string, AI-provider keys, or Slack webhook URL. The API is the controlled boundary between the authenticated dashboard and the database.

## Repository structure

```
.
├── pipeline/
│   ├── pipeline_runner.py       # bounded or interval-based pipeline execution
│   ├── config.py                # detector and provider configuration
│   ├── src/
│   │   ├── ingest.py            # market-data ingestion and provider failover
│   │   ├── quality.py            # data-quality checks
│   │   ├── anomaly.py            # deterministic anomaly detectors
│   │   ├── narrative.py          # structured AI narrative generation
│   │   └── db.py                 # local SQLite persistence
│   └── data/                    # local runtime database; do not commit secrets
├── hosted/
│   ├── api/
│   │   ├── app/main.py          # FastAPI service and protected evidence routes
│   │   ├── sql/                 # hosted schema and alert migrations
│   │   └── tools/               # synchronization and scheduled-cycle utilities
│   └── dashboard/
│       └── src/
│           ├── pages/Home.tsx   # Veyra page views and API integration
│           ├── components/      # shared layout and authentication UI
│           └── lib/api.ts       # authenticated frontend API client
├── .github/workflows/
│   └── crypto-monitor.yml       # scheduled monitoring workflow
├── render.yaml                  # Render service and scheduled-job configuration
├── vercel.json                  # Vercel SPA routing configuration
└── docs/                        # architecture, interview, and operational notes
```

## Data lifecycle

The Python pipeline fetches market observations from configured providers such as CoinGecko and Binance. Provider failover prevents one external API failure from silently stopping the monitoring cycle. Each observation carries asset, source, timestamp, price, volume, and related metadata.

Quality checks evaluate schema validity, value sanity, polling gaps, and other configured conditions. Invalid or suspicious inputs are recorded as quality flags so that downstream results can be interpreted in context.

The deterministic detector layer evaluates interpretable rules, including return-based z-score checks, IQR checks, and stablecoin peg-deviation logic. A detector finding is persisted with the values and references needed for later review.

Narratives are generated only when an anomaly requires analyst-readable context. The primary AI provider is used first, with a configured fallback when needed. Structured validation and provider metadata are retained rather than allowing an unstructured model response to decide whether an alert exists.

An alert intent is created only when the alert policy allows escalation. Its deterministic idempotency key prevents the same logical anomaly, alert type, and channel from creating duplicate alert records. Provider delivery is tracked separately through attempt rows.

## API endpoints

The following routes are exposed by the hosted FastAPI service.

| Method | Endpoint | Authentication | Purpose |
| --- | --- | --- | --- |
| `GET` | `/health` | Public | Basic service liveness and database/delivery posture |
| `GET` | `/api/readiness` | Public | Readiness checks for persistence, AI providers, and delivery configuration |
| `GET` | `/api/pipeline-runs?limit=8` | Bearer token | Return recent pipeline executions and stage counts |
| `GET` | `/api/anomalies?limit=50` | Bearer token | Return persisted anomaly findings |
| `GET` | `/api/narratives?limit=50` | Bearer token | Return persisted AI narratives and provider metadata |
| `GET` | `/api/alerts?limit=20` | Bearer token | Return persisted alert intents |
| `GET` | `/api/alert-delivery-attempts?limit=100` | Bearer token | Return provider attempt and response audit rows |
| `POST` | `/api/alerts` | Bearer token | Create an idempotent alert intent |
| `POST` | `/api/alerts/{alert_id}/deliver` | Bearer token | Attempt controlled delivery for an alert |
| `POST` | `/api/internal/alerts/dispatch` | Worker token | Dispatch eligible alerts from a trusted scheduler/worker path |

All list routes enforce bounded query limits. An oversized request such as `limit=1000000` is rejected with a validation response rather than returning an unbounded dataset.

## Authentication and CORS

Health and readiness are public so external monitoring can determine whether the service is alive and configured. Protected data routes require a Supabase access token in this form:

```
Authorization: Bearer <supabase-access-token>
```

The API middleware validates the token before the request reaches protected route handlers. The frontend obtains the session from Supabase Auth and attaches the token through the shared API client.

CORS preflight requests are allowed to complete, while the Render API allowlists the stable Vercel origin:

```
https://anomaly-plum.vercel.app
```

`location.origin` is useful during browser diagnosis because it tells us which exact frontend origin must be allowed by the API. It should not be hardcoded as a secret or used to bypass authentication.

## Database model

The hosted database preserves the lifecycle as separate records rather than collapsing everything into one status field.

| Table | Role |
| --- | --- |
| `pipeline_runs` | Execution identity, status, timing, and stage counts |
| `readings` | Raw or normalized market observations |
| `quality_flags` | Data-quality findings attached to observations or runs |
| `anomalies` | Deterministic detector findings and evidence |
| `narratives` | Structured AI explanations attached to findings |
| `alerts` | Idempotent logical alert intents and current state |
| `alert_delivery_attempts` | Individual provider attempts, response codes, errors, and timestamps |

The current Supabase tables have Row Level Security enabled. Explicit table policies and multi-tenant authorization should be designed and verified separately before treating the system as a general multi-user production platform.

## Alert state machine

Alert intent and provider delivery are separate concepts. An alert intent represents the decision to escalate. A delivery attempt represents one technical attempt to reach the provider.

```
pending → sending → sent
                  ↘ failed → retry according to policy
sent → acknowledged
```

The system records attempt number, provider, response code, safe error summary, start time, and finish time. The successful Slack canary produced one expected message, provider response `200`, and terminal alert status `sent`. Earlier `400` attempts remain visible because audit history should preserve both failure and recovery.

## Idempotency

The logical alert key follows this model:

```
anomaly_id:alert_type:channel
```

If the same pipeline event is processed twice, the second operation resolves to the existing alert intent rather than creating a duplicate logical alert. This protects Slack and future downstream systems from duplicate notifications when a scheduler retries, a client times out, or a deployment is repeated.

Technical retries are not duplicates. They are separate delivery-attempt rows under the same alert intent, which is why the audit can show `400 → 400 → 200` while the logical alert count remains one.

## Dashboard walkthrough

The recommended demonstration order is:

1. **Overview:** explain the production posture and distinguish the latest cycle from historical evidence.

1. **Pipeline runs:** show execution history and stage counts.

1. **Anomaly review:** show persisted detector findings, scores, references, and observation times.

1. **Narrative evidence:** show how AI makes a real finding understandable without deciding whether it is anomalous.

1. **Alert delivery:** show alert intents, idempotency, provider responses, retries, and the successful Slack audit.

1. **Runtime policy:** briefly show persistence, API reachability, AI configuration, server-side secret isolation, and live audited delivery.

A clean latest cycle may show zero new anomalies, narratives, and alerts. Historical pages remain populated because they query persisted records from earlier cycles.

## Local development

Create a Python virtual environment and install the pipeline/API dependencies according to the repository requirements file:

```
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Install dashboard dependencies and start the frontend/API development process according to the dashboard package scripts:

```
pnpm --dir .\hosted\dashboard install
pnpm --dir .\hosted\dashboard run dev
```

Never commit `.env` files, database passwords, access tokens, AI keys, service-role keys, or webhook URLs. Configure secrets through the hosting provider or local environment management.

## Verification commands

Run the following before committing a frontend change:

```
pnpm --dir .\hosted\dashboard run build
pnpm --dir .\hosted\dashboard run check
python -m compileall -q .\pipeline .\hosted\api
git diff --check
```

Run the bounded local monitoring cycle when the required provider and database configuration is available:

```
python .\hosted\api\tools\scheduled_cycle.py
```

Run a dry cycle when you want to validate control flow without live alert dispatch:

```
python .\hosted\api\tools\scheduled_cycle.py --dry-run
```

Before a final release, verify that local and remote Git state match:

```
git status --short --branch
git fetch origin
git rev-list --left-right --count HEAD...origin/main
```

The expected final state is a clean branch with divergence `0 0`.

## Deployment

The dashboard is deployed through Vercel and the API through Render. GitHub Actions runs the bounded monitoring workflow. Keep frontend and API environment variables separate: frontend configuration may contain only the public API base URL and public application configuration; database, AI, worker, and webhook secrets belong only to server-side environments.

A routine release should follow this order:

```
inspect status
→ run build and checks
→ inspect staged files
→ commit one focused change
→ push main
→ wait for Vercel/Render deployment
→ smoke-test health/readiness
→ sign in and verify all evidence pages
→ monitor alert delivery
```

Never publish secrets in workflow files. Do not manually alter the production database schema without a reviewed migration and a recovery plan.

## Security boundary

Veyra currently provides a portfolio-grade security boundary through authenticated API routes, validated access tokens, server-side credentials, explicit CORS, HTTPS, safe errors, bounded query limits, idempotent alerting, and delivery auditing.

The project should not be described as enterprise-certified. Before broader production use, add and test explicit Supabase policies, role-based access, organization/tenant isolation, rate limiting, security headers, dependency scanning, secret rotation, least-privilege database identities, webhook signing where supported, centralized logging, and broader automated tests.

## Limitations and future work

The current detector is an interpretable baseline rather than a learned predictive model. Evaluation against reviewed labels, alert precision, false-positive rate, detection delay, and analyst disposition would be the next analytical layer.

The portfolio release uses one authenticated analyst account. A multi-user platform would require roles, invitations, tenant isolation, row-level policies, human audit actors, and administrative workflows.

The next high-value product addition would be a Data Provenance page linking raw observation, provider, timestamp, quality status, pipeline run, detector finding, narrative, and alert. This would make the evidence chain even easier to inspect.

## Interview summary

> Veyra is an evidence-led digital-asset anomaly monitoring platform. It ingests market observations with provider failover, validates data quality, applies deterministic anomaly checks, persists findings, generates conditional AI narratives, and creates idempotent alerts with retry and delivery auditing. The core analytical decision remains reproducible and explainable, while the hosted control plane shows how that decision moves into a secure operational workflow.

The strongest design decision is the separation between detection and explanation. Statistical rules determine whether a finding exists. AI helps an analyst understand the finding. Alert policy decides whether escalation is appropriate. Delivery records prove what happened afterward.

## License and project status

This repository is a portfolio project. It is intended to demonstrate analytical reasoning, data-quality discipline, production-aware API design, secure configuration boundaries, alert reliability, and operational auditability.

The current release is complete as a portfolio demonstration. Future production hardening is documented above rather than implied or overstated.
