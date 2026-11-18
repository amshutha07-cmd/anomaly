from __future__ import annotations
import sys
from pathlib import Path as _Path

_ROOT = _Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import argparse
import asyncio
from contextlib import contextmanager
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import asyncpg
from dotenv import load_dotenv

import pipeline.config as config
from pipeline.src import db as local_db

DEFAULT_DB = Path("pipeline/data/pipeline_data.db")
RUN_NAMESPACE = uuid.UUID("6f4e31f2-41f7-4e25-b8a0-2f6b7ec0a2e8")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


@contextmanager
def open_sqlite(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"SQLite database not found: {path}")
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
    finally:
        connection.close()


async def warm_up_sqlite_from_supabase(
    sqlite_path: Path = DEFAULT_DB,
    database_url: str | None = None,
    min_readings_per_asset: int = 25,
) -> int:
    sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    local_db.init_db(str(sqlite_path))

    with open_sqlite(sqlite_path) as conn:
        btc_count = conn.execute(
            "SELECT COUNT(*) FROM crypto_prices WHERE asset_id = 'bitcoin' AND source = ?",
            (config.ANOMALY_SOURCE,),
        ).fetchone()[0]

    if btc_count >= min_readings_per_asset:
        return 0

    db_url = database_url or os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not db_url:
        return 0

    try:
        async with asyncpg.create_pool(db_url, min_size=1, max_size=2) as pool:
            async with pool.acquire() as pg_conn:
                rows = await pg_conn.fetch(
                    """
                    SELECT recorded_at, asset_id, source, price_usd,
                           volume_24h_usd, market_cap_usd, is_failover, fetch_latency_ms
                    FROM crypto_prices
                    ORDER BY recorded_at DESC
                    LIMIT $1
                    """,
                    min_readings_per_asset * 6,
                )
    except Exception as exc:
        print(f"INFO: Supabase warm-up skipped: {exc}")
        return 0

    if not rows:
        return 0

    readings_to_seed = []
    for r in reversed(rows):
        ts = r["recorded_at"].astimezone(timezone.utc).isoformat(timespec="seconds")
        readings_to_seed.append(
            {
                "recorded_at": ts,
                "asset_id": r["asset_id"],
                "source": r["source"],
                "price_usd": float(r["price_usd"]),
                "volume_24h_usd": float(r["volume_24h_usd"]) if r["volume_24h_usd"] is not None else None,
                "market_cap_usd": float(r["market_cap_usd"]) if r["market_cap_usd"] is not None else None,
                "is_failover": int(bool(r["is_failover"])),
                "fetch_latency_ms": float(r["fetch_latency_ms"]) if r["fetch_latency_ms"] is not None else 0.0,
            }
        )

    inserted, _ = local_db.insert_readings_batch(str(sqlite_path), readings_to_seed)
    print(f"Stateless Warm-Up: seeded {inserted} historical readings from Supabase into SQLite")
    return inserted


def read_local_snapshot(path: Path) -> dict[str, Any]:
    with open_sqlite(path) as conn:
        recent_readings = [
            dict(row)
            for row in conn.execute(
                """
                SELECT recorded_at, asset_id, source, price_usd,
                       volume_24h_usd, market_cap_usd, is_failover, fetch_latency_ms
                FROM crypto_prices
                ORDER BY recorded_at DESC
                LIMIT 180
                """
            )
        ]
        anomalies = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, recorded_at, asset_id, anomaly_type, observed_value,
                       reference_value, score, threshold_used, detail, created_at
                FROM anomalies ORDER BY id
                """
            )
        ]
        narratives = [
            dict(row)
            for row in conn.execute(
                """
                SELECT anomaly_id, severity, likely_cause, recommended_action,
                       narrative, provider_used, model_used, latency_ms,
                       prompt_tokens, completion_tokens, fallback_used
                FROM narratives ORDER BY anomaly_id
                """
            )
        ]
        readings_count = conn.execute("SELECT COUNT(*) FROM crypto_prices").fetchone()[0]
        quality_flags_count = conn.execute("SELECT COUNT(*) FROM quality_flags").fetchone()[0]
        latest_reading = (
            conn.execute("SELECT MAX(recorded_at) FROM crypto_prices").fetchone()[0]
            or "empty"
        )

    snapshot_key = f"{path.resolve()}|{latest_reading}|{readings_count}|{quality_flags_count}|{len(anomalies)}|{len(narratives)}"
    run_id = uuid.uuid5(RUN_NAMESPACE, snapshot_key)
    return {
        "run_id": run_id,
        "recent_readings": recent_readings,
        "anomalies": anomalies,
        "narratives": narratives,
        "readings_count": readings_count,
        "quality_flags_count": quality_flags_count,
        "latest_reading": latest_reading,
        "snapshot_key": snapshot_key,
    }


def require_database_url() -> str:
    url = os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "SUPABASE_DATABASE_URL or DATABASE_URL is missing. "
            "Set it locally from the Supabase connection-string panel; never commit it."
        )
    return url


async def sync_snapshot(snapshot: dict[str, Any], database_url: str) -> None:
    now = utc_now()
    async with asyncpg.create_pool(database_url, min_size=1, max_size=2) as pool:
        async with pool.acquire() as conn:
            # Isolated transaction 1: Ensure crypto_prices exists and sync recent readings for warm-up
            try:
                async with conn.transaction():
                    await conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS crypto_prices (
                            recorded_at TIMESTAMPTZ NOT NULL,
                            asset_id TEXT NOT NULL,
                            source TEXT NOT NULL,
                            price_usd DOUBLE PRECISION NOT NULL,
                            volume_24h_usd DOUBLE PRECISION,
                            market_cap_usd DOUBLE PRECISION,
                            is_failover BOOLEAN NOT NULL DEFAULT FALSE,
                            fetch_latency_ms DOUBLE PRECISION,
                            PRIMARY KEY (recorded_at, asset_id, source)
                        )
                        """
                    )
                    for r in snapshot.get("recent_readings", []):
                        await conn.execute(
                            """
                            INSERT INTO crypto_prices (
                                recorded_at, asset_id, source, price_usd,
                                volume_24h_usd, market_cap_usd, is_failover, fetch_latency_ms
                            ) VALUES ($1::timestamptz, $2, $3, $4, $5, $6, $7, $8)
                            ON CONFLICT (recorded_at, asset_id, source) DO NOTHING
                            """,
                            parse_timestamp(r["recorded_at"]),
                            r["asset_id"],
                            r["source"],
                            r["price_usd"],
                            r["volume_24h_usd"],
                            r["market_cap_usd"],
                            bool(r["is_failover"]),
                            r["fetch_latency_ms"],
                        )
            except Exception as exc:
                print(f"INFO: Optional crypto_prices warm-up table sync skipped: {exc}")

            # Isolated transaction 2: Canonical anomalies, narratives, and pipeline_runs sync
            async with conn.transaction():
                for anomaly in snapshot["anomalies"]:
                    await conn.execute(
                        """
                        INSERT INTO anomalies (
                            id, recorded_at, asset_id, anomaly_type,
                            observed_value, reference_value, score,
                            threshold_used, detail, created_at
                        ) VALUES ($1,$2::timestamptz,$3,$4,$5,$6,$7,$8,$9,$10::timestamptz)
                        ON CONFLICT (id) DO UPDATE SET
                            recorded_at = EXCLUDED.recorded_at,
                            asset_id = EXCLUDED.asset_id,
                            anomaly_type = EXCLUDED.anomaly_type,
                            observed_value = EXCLUDED.observed_value,
                            reference_value = EXCLUDED.reference_value,
                            score = EXCLUDED.score,
                            threshold_used = EXCLUDED.threshold_used,
                            detail = EXCLUDED.detail,
                            created_at = EXCLUDED.created_at
                        """,
                        anomaly["id"],
                        parse_timestamp(anomaly["recorded_at"]),
                        anomaly["asset_id"],
                        anomaly["anomaly_type"],
                        anomaly["observed_value"],
                        anomaly["reference_value"],
                        anomaly["score"],
                        anomaly["threshold_used"],
                        anomaly["detail"],
                        parse_timestamp(anomaly["created_at"]),
                    )

                for narrative in snapshot["narratives"]:
                    await conn.execute(
                        """
                        INSERT INTO narratives (
                            anomaly_id, severity, likely_cause,
                            recommended_action, narrative, provider_used,
                            model_used, latency_ms, prompt_tokens,
                            completion_tokens, fallback_used
                        ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
                        ON CONFLICT (anomaly_id) DO UPDATE SET
                            severity = EXCLUDED.severity,
                            likely_cause = EXCLUDED.likely_cause,
                            recommended_action = EXCLUDED.recommended_action,
                            narrative = EXCLUDED.narrative,
                            provider_used = EXCLUDED.provider_used,
                            model_used = EXCLUDED.model_used,
                            latency_ms = EXCLUDED.latency_ms,
                            prompt_tokens = EXCLUDED.prompt_tokens,
                            completion_tokens = EXCLUDED.completion_tokens,
                            fallback_used = EXCLUDED.fallback_used
                        """,
                        narrative["anomaly_id"],
                        narrative["severity"],
                        narrative["likely_cause"],
                        narrative["recommended_action"],
                        narrative["narrative"],
                        narrative["provider_used"] or "legacy_import",
                        narrative["model_used"] or "unknown",
                        narrative["latency_ms"] if narrative["latency_ms"] is not None else 0.0,
                        narrative["prompt_tokens"] if narrative["prompt_tokens"] is not None else 0,
                        narrative["completion_tokens"] if narrative["completion_tokens"] is not None else 0,
                        bool(narrative["fallback_used"]),
                    )

                await conn.execute(
                    """
                    INSERT INTO pipeline_runs (
                        run_id, started_at, completed_at, status,
                        readings_fetched, readings_inserted,
                        quality_flags_count, anomalies_count, narratives_count,
                        alerts_created, alerts_sent, alerts_failed,
                        stage_timings_ms, error_summary
                    ) VALUES ($1,$2,$3,'succeeded',$4,$4,$5,$6,$7,0,0,0,$8::jsonb,NULL)
                    ON CONFLICT (run_id) DO UPDATE SET
                        completed_at = EXCLUDED.completed_at,
                        status = EXCLUDED.status,
                        readings_fetched = EXCLUDED.readings_fetched,
                        readings_inserted = EXCLUDED.readings_inserted,
                        quality_flags_count = EXCLUDED.quality_flags_count,
                        anomalies_count = EXCLUDED.anomalies_count,
                        narratives_count = EXCLUDED.narratives_count,
                        stage_timings_ms = EXCLUDED.stage_timings_ms,
                        error_summary = NULL
                    """,
                    snapshot["run_id"],
                    now,
                    now,
                    snapshot["readings_count"],
                    snapshot["quality_flags_count"],
                    len(snapshot["anomalies"]),
                    len(snapshot["narratives"]),
                    json.dumps({"sync": 0.0}),
                )


def main() -> None:
    parser = argparse.ArgumentParser(description="Sync legitimate local Modules 1-4 output to Supabase")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--warm-up", action="store_true", help="Seed local SQLite from Supabase if cold")
    args = parser.parse_args()

    load_dotenv(dotenv_path=".env", override=False)
    if args.warm_up:
        asyncio.run(warm_up_sqlite_from_supabase(args.db))
        return

    snapshot = read_local_snapshot(args.db)
    print(
        f"Local snapshot: readings={snapshot['readings_count']}, "
        f"quality_flags={snapshot['quality_flags_count']}, "
        f"anomalies={len(snapshot['anomalies'])}, "
        f"narratives={len(snapshot['narratives'])}, "
        f"run_id={snapshot['run_id']}"
    )
    if args.dry_run:
        print("DRY RUN: no Supabase writes performed")
        return

    asyncio.run(sync_snapshot(snapshot, require_database_url()))
    print("SUPABASE SYNC COMPLETE: readings, anomalies, narratives, and pipeline_run upserted idempotently")


if __name__ == "__main__":
    main()
