from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg
import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
load_dotenv(ROOT / ".env")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def run_command(args: list[str]) -> None:
    print("RUN:", " ".join(args))
    subprocess.run(args, cwd=ROOT, check=True)


async def create_alert_intents(since: datetime) -> list[str]:
    database_url = require("SUPABASE_DATABASE_URL")
    created: list[str] = []
    async with asyncpg.create_pool(database_url, min_size=1, max_size=2) as pool:
        async with pool.acquire() as conn:
            run_id = await conn.fetchval(
                "SELECT run_id FROM pipeline_runs ORDER BY started_at DESC LIMIT 1"
            )
            rows = await conn.fetch(
                """
                SELECT a.id AS anomaly_id,
                       a.anomaly_type,
                       n.anomaly_id AS narrative_id,
                       COALESCE(n.severity, 'medium') AS severity
                FROM anomalies a
                LEFT JOIN narratives n ON n.anomaly_id = a.id
                WHERE a.created_at >= $1
                  AND NOT EXISTS (
                      SELECT 1
                      FROM alerts existing
                      WHERE existing.anomaly_id = a.id
                        AND existing.alert_type = 'scheduled_' || a.anomaly_type
                        AND existing.channel = 'webhook'
                  )
                ORDER BY a.id
                """,
                since,
            )
            for row in rows:
                alert_id = uuid.uuid4()
                alert_type = f"scheduled_{row['anomaly_type']}"
                idempotency_key = f"{row['anomaly_id']}:{alert_type}:webhook"
                inserted = await conn.fetchval(
                    """
                    INSERT INTO alerts (
                        alert_id, anomaly_id, narrative_id, run_id,
                        alert_type, severity, channel,
                        idempotency_key, status
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,'webhook',$7,'pending')
                    ON CONFLICT (idempotency_key) DO NOTHING
                    RETURNING alert_id
                    """,
                    alert_id,
                    row["anomaly_id"],
                    row["narrative_id"],
                    run_id,
                    alert_type,
                    row["severity"],
                    idempotency_key,
                )
                if inserted:
                    created.append(str(inserted))
    return created


def dispatch_alerts(dry_run: bool) -> dict:
    if dry_run:
        return {"skipped": True, "reason": "dry_run"}
    api_base = require("HOSTED_API_BASE_URL").rstrip("/")
    worker_token = require("ALERT_WORKER_TOKEN")
    response = requests.post(
        f"{api_base}/api/internal/alerts/dispatch?limit=100",
        headers={"x-alert-worker-token": worker_token},
        timeout=30,
    )
    if not 200 <= response.status_code < 300:
        raise RuntimeError(f"dispatch failed with HTTP {response.status_code}")
    return response.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run one hosted anomaly-monitor cycle")
    parser.add_argument("--dry-run", action="store_true", help="run and sync, but never call the dispatcher")
    args = parser.parse_args()

    data_dir = ROOT / "pipeline" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    cycle_started = utc_now() - timedelta(minutes=2)
    run_command([sys.executable, "-m", "pipeline.pipeline_runner", "--single-run"])
    run_command([sys.executable, "hosted/api/tools/sync_pipeline_to_supabase.py"])
    created = asyncio.run(create_alert_intents(cycle_started))
    result = dispatch_alerts(args.dry_run)
    print({"alert_intents_created": len(created), "alert_ids": created, "dispatch": result})


if __name__ == "__main__":
    main()
