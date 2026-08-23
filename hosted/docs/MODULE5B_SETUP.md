# Module 5B setup

Module 5B is implemented with external delivery disabled by default. The state machine is:

`pending â†’ sending â†’ sent â†’ acknowledged`

A provider failure records `failed`, stores a sanitized error, and schedules an exponential-backoff retry until `ALERT_MAX_ATTEMPTS` is reached. Duplicate alert creation remains controlled by the existing idempotency key.

## Required environment variables

Keep these disabled/unset during testing:

```text
ALERT_DELIVERY_ENABLED=false
```

When a real webhook is intentionally approved later, configure these only in Render Environment, never in Git:

```text
ALERT_DELIVERY_ENABLED=true
ALERT_WEBHOOK_URL=https://your-approved-webhook.example/endpoint
ALERT_WORKER_TOKEN=<long-random-server-only-token>
ALERT_MAX_ATTEMPTS=5
ALERT_RETRY_BACKOFF_SECONDS=30
```

The delivery endpoint is `POST /api/alerts/{alert_id}/deliver`. The acknowledgement endpoint is `PATCH /api/alerts/{alert_id}/acknowledge`. The retry worker endpoint is `POST /api/internal/alerts/dispatch`; it accepts either the normal Supabase bearer token or the server-only `X-Alert-Worker-Token` when that variable is configured.

No external request is made while `ALERT_DELIVERY_ENABLED=false`.