"""
Pipeline orchestrator for Veyra.

Usage:
    python -m pipeline.pipeline_runner --single-run
    python -m pipeline.pipeline_runner --interval 60

Error isolation: failures in ingestion, DB persistence, quality checks,
anomaly detection, or narrative generation are caught and logged per-stage
so a single degraded poll never crashes the monitoring loop.
"""

import argparse
import logging
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()

import pipeline.config as config
from pipeline.src import anomaly, db, ingest, narrative, quality

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pipeline_runner")


def run_once() -> None:
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log.info("=== poll start: %s ===", recorded_at)

    try:
        fetch_start = time.perf_counter()
        readings = ingest.fetch_all(recorded_at)
        fetch_stage_ms = (time.perf_counter() - fetch_start) * 1000
    except Exception:
        log.exception("Ingestion stage failed entirely for this poll - skipping DB write")
        return

    if not readings:
        log.warning("No readings collected this poll (all sources failed) - nothing to write")
        return

    try:
        write_start = time.perf_counter()
        inserted, skipped = db.insert_readings_batch(config.DB_PATH, readings)
        write_stage_ms = (time.perf_counter() - write_start) * 1000
    except Exception:
        log.exception("DB write stage failed - readings collected but not persisted this poll")
        return

    failover_count = sum(1 for r in readings if r["is_failover"])
    log.info(
        "poll done: %d fetched, %d inserted, %d skipped (dup), %d via failover | "
        "fetch_stage=%.1fms write_stage=%.1fms",
        len(readings), inserted, skipped, failover_count, fetch_stage_ms, write_stage_ms,
    )

    try:
        quality_start = time.perf_counter()
        flags = quality.run_all_checks(config.DB_PATH, recorded_at, readings)
        quality_stage_ms = (time.perf_counter() - quality_start) * 1000
        log.info(
            "quality checks done: %d flag(s) raised | quality_stage=%.1fms",
            len(flags), quality_stage_ms,
        )
    except Exception:
        log.exception("Quality-check stage failed - this poll's data is persisted but unvalidated")

    anomalies = []
    try:
        anomaly_start = time.perf_counter()
        anomalies = anomaly.run_all_checks(config.DB_PATH, recorded_at, readings)
        anomaly_stage_ms = (time.perf_counter() - anomaly_start) * 1000
        log.info(
            "anomaly checks done: %d anomaly(ies) detected | anomaly_stage=%.1fms",
            len(anomalies), anomaly_stage_ms,
        )
    except Exception:
        log.exception("Anomaly-detection stage failed - this poll's data is persisted but not scored")

    if anomalies:
        try:
            narrative_start = time.perf_counter()
            narratives = narrative.attach_history_and_generate(config.DB_PATH, anomalies)
            narrative_stage_ms = (time.perf_counter() - narrative_start) * 1000
            log.info(
                "narrative generation done: %d narrative(s) | narrative_stage=%.1fms",
                len(narratives), narrative_stage_ms,
            )
        except Exception:
            log.exception("Narrative-generation stage failed - anomalies persisted but unexplained")


def run_loop(interval_seconds: int) -> None:
    log.info("Starting continuous polling every %ds (Ctrl+C to stop)", interval_seconds)
    try:
        while True:
            run_once()
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        log.info("Stopped by user")


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto anomaly-detection pipeline runner")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--single-run", action="store_true", help="Run one poll and exit")
    group.add_argument("--interval", type=int, help="Run continuously every N seconds")
    args = parser.parse_args()

    db.init_db(config.DB_PATH)

    if args.single_run:
        run_once()
    else:
        run_loop(args.interval)


if __name__ == "__main__":
    main()
