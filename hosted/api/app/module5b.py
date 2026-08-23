from __future__ import annotations

import asyncio
import hashlib
import hmac
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import asyncpg
import requests


SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|authorization|password|secret|token)\s*[=:]\s*[^\s,;]+|bearer\s+[^\s,;]+"
)
MAX_ERROR_LENGTH = 500


def delivery_enabled() -> bool:
    """External delivery is opt-in and remains disabled unless explicitly enabled."""
    return os.getenv("ALERT_DELIVERY_ENABLED", "false").strip().lower() == "true"


def worker_token_matches(value: str | None) -> bool:
    expected = os.getenv("ALERT_WORKER_TOKEN", "")
    if not expected or not value:
        return False
    return hmac.compare_digest(value, expected)


def max_attempts() -> int:
    try:
        return max(1, min(int(os.getenv("ALERT_MAX_ATTEMPTS", "5")), 20))
    except ValueError:
        return 5


def retry_delay_seconds(attempt_number: int) -> int:
    try:
        base = max(1, int(os.getenv("ALERT_RETRY_BACKOFF_SECONDS", "30")))
    except ValueError:
        base = 30
    return min(base * (2 ** max(0, attempt_number - 1)), 3600)


def safe_error_summary(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = SECRET_PATTERN.sub("[REDACTED]", str(value))
    cleaned = re.sub(r"https?://\S+", "[URL_REDACTED]", cleaned)
    return cleaned[:MAX_ERROR_LENGTH]


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime) else value


def build_webhook_payload(row: dict[str, Any]) -> dict[str, Any]:
    """Build the minimal Slack Incoming Webhook message body.

    Slack requires a top-level ``text`` field. Keep the payload deliberately
    small and operational; never include webhook URLs, tokens, or DB secrets.
    """
    severity = str(row.get("severity") or "unknown").upper()
    alert_id = str(row["alert_id"])
    anomaly_id = str(row["anomaly_id"])
    alert_type = str(row["alert_type"])
    idempotency_key = str(row["idempotency_key"])
    return {
        "text": (
            f"Crypto anomaly alert | severity={severity} | "
            f"alert_id={alert_id} | anomaly_id={anomaly_id} | "
            f"alert_type={alert_type} | idempotency_key={idempotency_key}"
        )
    }


def _post_webhook(url: str, payload: dict[str, Any]) -> tuple[bool, int | None, str | None]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False, None, "ALERT_WEBHOOK_URL must be an http or https URL"
    try:
        response = requests.post(
            url,
            json=payload,
            headers={"Content-Type": "application/json", "X-Alert-Event": "crypto_anomaly"},
            timeout=10,
        )
        if 200 <= response.status_code < 300:
            return True, response.status_code, None
        provider_detail = (response.text or "").strip().replace("\r", " ").replace("\n", " ")
        provider_detail = provider_detail[:160]
        return False, response.status_code, safe_error_summary(
            f"Webhook returned HTTP {response.status_code}: {provider_detail}"
        )
    except Exception as exc:  # network/provider errors are recorded, not exposed raw
        return False, None, safe_error_summary(str(exc)) or "Webhook delivery failed"


async def _fetch_alert(pool: asyncpg.Pool, alert_id: uuid.UUID) -> dict[str, Any] | None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT * FROM alerts WHERE alert_id = $1", alert_id)
    return dict(row) if row else None


def _result(
    row: dict[str, Any],
    status: str,
    delivered: bool,
    dry_run: bool,
    message: str,
    retry_scheduled: bool = False,
) -> dict[str, Any]:
    return {
        "alert": row,
        "status": status,
        "delivered": delivered,
        "dry_run": dry_run,
        "retry_scheduled": retry_scheduled,
        "message": message,
    }


async def deliver_alert(pool: asyncpg.Pool, alert_id: uuid.UUID) -> dict[str, Any] | None:
    """Claim one alert, deliver it once, and persist the outcome idempotently."""
    current = await _fetch_alert(pool, alert_id)
    if current is None:
        return None

    if not delivery_enabled():
        return _result(
            current,
            "dry_run",
            False,
            True,
            "Automatic alert delivery is disabled; no external request was made.",
        )

    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        claimed = await conn.fetchrow(
            """
            UPDATE alerts
               SET status = 'sending',
                   attempt_count = attempt_count + 1,
                   last_attempt_at = $2,
                   last_error = NULL
             WHERE alert_id = $1
               AND status IN ('pending', 'failed')
               AND attempt_count < $3
               AND (next_attempt_at IS NULL OR next_attempt_at <= $2)
            RETURNING *
            """,
            alert_id,
            now,
            max_attempts(),
        )

    if claimed is None:
        current = await _fetch_alert(pool, alert_id)
        if current is None:
            return None
        if current["status"] in {"sent", "acknowledged"}:
            return _result(current, current["status"], True, False, "Alert was already delivered.")
        return _result(current, current["status"], False, False, "Alert is already being processed or is not due yet.")

    claimed_dict = dict(claimed)
    attempt_id = uuid.uuid4()
    attempt_number = int(claimed_dict["attempt_count"])
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO alert_delivery_attempts
                (attempt_id, alert_id, attempt_number, status, provider, started_at)
            VALUES ($1, $2, $3, 'started', 'webhook', $4)
            """,
            attempt_id,
            alert_id,
            attempt_number,
            now,
        )

    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "")
    success, response_code, error = await asyncio.to_thread(
        _post_webhook,
        webhook_url,
        build_webhook_payload(claimed_dict),
    )
    finished = datetime.now(timezone.utc)
    retry_scheduled = False

    if success:
        next_attempt = None
        status = "sent"
        sent_at = finished
        message = "Alert delivered successfully."
    else:
        status = "failed"
        sent_at = None
        if attempt_number < max_attempts():
            next_attempt = finished + timedelta(seconds=retry_delay_seconds(attempt_number))
            retry_scheduled = True
            message = "Alert delivery failed; retry scheduled."
        else:
            next_attempt = None
            message = "Alert delivery failed; maximum attempts reached."

    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE alerts
               SET status = $2,
                   sent_at = $3,
                   next_attempt_at = $4,
                   last_error = $5
             WHERE alert_id = $1
            """,
            alert_id,
            status,
            sent_at,
            next_attempt,
            error,
        )
        await conn.execute(
            """
            UPDATE alert_delivery_attempts
               SET status = $2,
                   response_code = $3,
                   error_summary = $4,
                   finished_at = $5
             WHERE attempt_id = $1
            """,
            attempt_id,
            "sent" if success else "failed",
            response_code,
            error,
            finished,
        )
        row = await conn.fetchrow("SELECT * FROM alerts WHERE alert_id = $1", alert_id)

    return _result(
        dict(row),
        status,
        success,
        False,
        message,
        retry_scheduled,
    )


async def acknowledge_alert(pool: asyncpg.Pool, alert_id: uuid.UUID) -> dict[str, Any] | None:
    current = await _fetch_alert(pool, alert_id)
    if current is None:
        return None
    if current["status"] == "acknowledged":
        return current
    if current["status"] != "sent":
        current["_error"] = "Only a sent alert can be acknowledged"
        return current

    now = datetime.now(timezone.utc)
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            UPDATE alerts
               SET status = 'acknowledged', acknowledged_at = $2
             WHERE alert_id = $1 AND status = 'sent'
            RETURNING *
            """,
            alert_id,
            now,
        )
    return dict(row) if row else await _fetch_alert(pool, alert_id)


async def dispatch_due_alerts(pool: asyncpg.Pool, limit: int = 20) -> list[dict[str, Any]]:
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT alert_id
              FROM alerts
             WHERE status IN ('pending', 'failed')
               AND attempt_count < $1
               AND (next_attempt_at IS NULL OR next_attempt_at <= now())
             ORDER BY created_at ASC
             LIMIT $2
            """,
            max_attempts(),
            limit,
        )
    results: list[dict[str, Any]] = []
    for row in rows:
        result = await deliver_alert(pool, row["alert_id"])
        if result is not None:
            results.append(result)
    return results