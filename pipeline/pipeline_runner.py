# # # # """
# # # # Pipeline orchestrator.

# # # # Usage:
# # # #     python pipeline_runner.py --single-run
# # # #     python pipeline_runner.py --interval 60

# # # # Error isolation: a failure in ingestion (e.g. both sources down) or in
# # # # DB write is caught and logged per-poll, not allowed to crash the loop.
# # # # A bad poll should never take down future polls or lose already-written
# # # # data â€” same principle as Module 1's original design, just now applied
# # # # across two sources instead of one.
# # # # """

# # # # import argparse
# # # # import logging
# # # # import time
# # # # from datetime import datetime, timezone

# # # # import pipeline.config as config
# # # # from pipeline.src import db, ingest

# # # # logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# # # # log = logging.getLogger("pipeline_runner")


# # # # def run_once() -> None:
# # # #     recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
# # # #     log.info("=== poll start: %s ===", recorded_at)

# # # #     # --- Stage 1: ingestion (own try/except so a fetch failure
# # # #     # doesn't prevent the DB layer or the next poll from running) ---
# # # #     try:
# # # #         fetch_start = time.perf_counter()
# # # #         readings = ingest.fetch_all(recorded_at)
# # # #         fetch_stage_ms = (time.perf_counter() - fetch_start) * 1000
# # # #     except Exception:
# # # #         log.exception("Ingestion stage failed entirely for this poll â€” skipping DB write")
# # # #         return

# # # #     if not readings:
# # # #         log.warning("No readings collected this poll (all sources failed) â€” nothing to write")
# # # #         return

# # # #     # --- Stage 2: DB write (measured separately from fetch, per the
# # # #     # Module 1 latency-profiling design â€” lets us say precisely where
# # # #     # time is going, and whether failover polls are slower end-to-end) ---
# # # #     try:
# # # #         write_start = time.perf_counter()
# # # #         inserted, skipped = db.insert_readings_batch(config.DB_PATH, readings)
# # # #         write_stage_ms = (time.perf_counter() - write_start) * 1000
# # # #     except Exception:
# # # #         log.exception("DB write stage failed â€” readings collected but not persisted this poll")
# # # #         return

# # # #     failover_count = sum(1 for r in readings if r["is_failover"])
# # # #     log.info(
# # # #         "poll done: %d fetched, %d inserted, %d skipped (dup), %d via failover | "
# # # #         "fetch_stage=%.1fms write_stage=%.1fms",
# # # #         len(readings), inserted, skipped, failover_count, fetch_stage_ms, write_stage_ms,
# # # #     )


# # # # def run_loop(interval_seconds: int) -> None:
# # # #     log.info("Starting continuous polling every %ds (Ctrl+C to stop)", interval_seconds)
# # # #     try:
# # # #         while True:
# # # #             run_once()
# # # #             time.sleep(interval_seconds)
# # # #     except KeyboardInterrupt:
# # # #         log.info("Stopped by user")


# # # # def main():
# # # #     parser = argparse.ArgumentParser(description="Crypto anomaly-detection pipeline runner")
# # # #     group = parser.add_mutually_exclusive_group(required=True)
# # # #     group.add_argument("--single-run", action="store_true", help="Run one poll and exit")
# # # #     group.add_argument("--interval", type=int, help="Run continuously every N seconds")
# # # #     args = parser.parse_args()

# # # #     db.init_db(config.DB_PATH)

# # # #     if args.single_run:
# # # #         run_once()
# # # #     else:
# # # #         run_loop(args.interval)


# # # # if __name__ == "__main__":
# # # #     main()
# # # """
# # # Pipeline orchestrator.

# # # Usage:
# # #     python pipeline_runner.py --single-run
# # #     python pipeline_runner.py --interval 60

# # # Error isolation: a failure in ingestion (e.g. both sources down) or in
# # # DB write is caught and logged per-poll, not allowed to crash the loop.
# # # A bad poll should never take down future polls or lose already-written
# # # data â€” same principle as Module 1's original design, just now applied
# # # across two sources instead of one.
# # # """

# # # import argparse
# # # import logging
# # # import time
# # # from datetime import datetime, timezone

# # # import pipeline.config as config
# # # from pipeline.src import db, ingest, quality

# # # logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# # # log = logging.getLogger("pipeline_runner")


# # # def run_once() -> None:
# # #     recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
# # #     log.info("=== poll start: %s ===", recorded_at)

# # #     # --- Stage 1: ingestion (own try/except so a fetch failure
# # #     # doesn't prevent the DB layer or the next poll from running) ---
# # #     try:
# # #         fetch_start = time.perf_counter()
# # #         readings = ingest.fetch_all(recorded_at)
# # #         fetch_stage_ms = (time.perf_counter() - fetch_start) * 1000
# # #     except Exception:
# # #         log.exception("Ingestion stage failed entirely for this poll â€” skipping DB write")
# # #         return

# # #     if not readings:
# # #         log.warning("No readings collected this poll (all sources failed) â€” nothing to write")
# # #         return

# # #     # --- Stage 2: DB write (measured separately from fetch, per the
# # #     # Module 1 latency-profiling design â€” lets us say precisely where
# # #     # time is going, and whether failover polls are slower end-to-end) ---
# # #     try:
# # #         write_start = time.perf_counter()
# # #         inserted, skipped = db.insert_readings_batch(config.DB_PATH, readings)
# # #         write_stage_ms = (time.perf_counter() - write_start) * 1000
# # #     except Exception:
# # #         log.exception("DB write stage failed â€” readings collected but not persisted this poll")
# # #         return

# # #     failover_count = sum(1 for r in readings if r["is_failover"])
# # #     log.info(
# # #         "poll done: %d fetched, %d inserted, %d skipped (dup), %d via failover | "
# # #         "fetch_stage=%.1fms write_stage=%.1fms",
# # #         len(readings), inserted, skipped, failover_count, fetch_stage_ms, write_stage_ms,
# # #     )

# # #     # --- Stage 3: data quality checks (own try/except â€” a bug in a
# # #     # quality check should never take down ingestion; readings are
# # #     # already safely persisted by this point regardless of what
# # #     # Module 2 finds) ---
# # #     try:
# # #         quality_start = time.perf_counter()
# # #         flags = quality.run_all_checks(config.DB_PATH, recorded_at, readings)
# # #         quality_stage_ms = (time.perf_counter() - quality_start) * 1000
# # #         log.info(
# # #             "quality checks done: %d flag(s) raised | quality_stage=%.1fms",
# # #             len(flags), quality_stage_ms,
# # #         )
# # #     except Exception:
# # #         log.exception("Quality-check stage failed â€” this poll's data is persisted but unvalidated")


# # # def run_loop(interval_seconds: int) -> None:
# # #     log.info("Starting continuous polling every %ds (Ctrl+C to stop)", interval_seconds)
# # #     try:
# # #         while True:
# # #             run_once()
# # #             time.sleep(interval_seconds)
# # #     except KeyboardInterrupt:
# # #         log.info("Stopped by user")


# # # def main():
# # #     parser = argparse.ArgumentParser(description="Crypto anomaly-detection pipeline runner")
# # #     group = parser.add_mutually_exclusive_group(required=True)
# # #     group.add_argument("--single-run", action="store_true", help="Run one poll and exit")
# # #     group.add_argument("--interval", type=int, help="Run continuously every N seconds")
# # #     args = parser.parse_args()

# # #     db.init_db(config.DB_PATH)

# # #     if args.single_run:
# # #         run_once()
# # #     else:
# # #         run_loop(args.interval)


# # # if __name__ == "__main__":
# # #     main()
# # """
# # Pipeline orchestrator.

# # Usage:
# #     python pipeline_runner.py --single-run
# #     python pipeline_runner.py --interval 60

# # Error isolation: a failure in ingestion (e.g. both sources down) or in
# # DB write is caught and logged per-poll, not allowed to crash the loop.
# # A bad poll should never take down future polls or lose already-written
# # data â€” same principle as Module 1's original design, just now applied
# # across two sources instead of one.
# # """

# # import argparse
# # import logging
# # import time
# # from datetime import datetime, timezone

# # import pipeline.config as config
# # from pipeline.src import anomaly, db, ingest, quality,narrative

# # logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# # log = logging.getLogger("pipeline_runner")


# # def run_once() -> None:
# #     recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
# #     log.info("=== poll start: %s ===", recorded_at)

# #     # --- Stage 1: ingestion (own try/except so a fetch failure
# #     # doesn't prevent the DB layer or the next poll from running) ---
# #     try:
# #         fetch_start = time.perf_counter()
# #         readings = ingest.fetch_all(recorded_at)
# #         fetch_stage_ms = (time.perf_counter() - fetch_start) * 1000
# #     except Exception:
# #         log.exception("Ingestion stage failed entirely for this poll â€” skipping DB write")
# #         return

# #     if not readings:
# #         log.warning("No readings collected this poll (all sources failed) â€” nothing to write")
# #         return

# #     # --- Stage 2: DB write (measured separately from fetch, per the
# #     # Module 1 latency-profiling design â€” lets us say precisely where
# #     # time is going, and whether failover polls are slower end-to-end) ---
# #     try:
# #         write_start = time.perf_counter()
# #         inserted, skipped = db.insert_readings_batch(config.DB_PATH, readings)
# #         write_stage_ms = (time.perf_counter() - write_start) * 1000
# #     except Exception:
# #         log.exception("DB write stage failed â€” readings collected but not persisted this poll")
# #         return

# #     failover_count = sum(1 for r in readings if r["is_failover"])
# #     log.info(
# #         "poll done: %d fetched, %d inserted, %d skipped (dup), %d via failover | "
# #         "fetch_stage=%.1fms write_stage=%.1fms",
# #         len(readings), inserted, skipped, failover_count, fetch_stage_ms, write_stage_ms,
# #     )

# #     # --- Stage 3: data quality checks (own try/except â€” a bug in a
# #     # quality check should never take down ingestion; readings are
# #     # already safely persisted by this point regardless of what
# #     # Module 2 finds) ---
# #     try:
# #         quality_start = time.perf_counter()
# #         flags = quality.run_all_checks(config.DB_PATH, recorded_at, readings)
# #         quality_stage_ms = (time.perf_counter() - quality_start) * 1000
# #         log.info(
# #             "quality checks done: %d flag(s) raised | quality_stage=%.1fms",
# #             len(flags), quality_stage_ms,
# #         )
# #     except Exception:
# #         log.exception("Quality-check stage failed â€” this poll's data is persisted but unvalidated")

# #     # --- Stage 4: anomaly detection (own try/except â€” same isolation
# #     # principle as every prior stage; a bug here shouldn't undo the
# #     # ingestion or quality-check work already done this poll) ---
# #     try:
# #         anomaly_start = time.perf_counter()
# #         anomalies = anomaly.run_all_checks(config.DB_PATH, recorded_at, readings)
# #         anomaly_stage_ms = (time.perf_counter() - anomaly_start) * 1000
# #         log.info(
# #             "anomaly checks done: %d anomaly(ies) detected | anomaly_stage=%.1fms",
# #             len(anomalies), anomaly_stage_ms,
# #         )
# #     except Exception:
# #         log.exception("Anomaly-detection stage failed â€” this poll's data is persisted but not scored")


# # def run_loop(interval_seconds: int) -> None:
# #     log.info("Starting continuous polling every %ds (Ctrl+C to stop)", interval_seconds)
# #     try:
# #         while True:
# #             run_once()
# #             time.sleep(interval_seconds)
# #     except KeyboardInterrupt:
# #         log.info("Stopped by user")

# # # --- Stage 5: narrative generation (own try/except â€” same isolation
# #     # principle as every prior stage; an LLM failure shouldn't lose the
# #     # anomaly data already persisted) ---
# #     if anomalies:
# #         try:
# #             narrative_start = time.perf_counter()
# #             narratives = narrative.attach_history_and_generate(config.DB_PATH, anomalies)
# #             narrative_stage_ms = (time.perf_counter() - narrative_start) * 1000
# #             log.info(
# #                 "narrative generation done: %d narrative(s) | narrative_stage=%.1fms",
# #                 len(narratives), narrative_stage_ms,
# #             )
# #         except Exception:
# #             log.exception("Narrative-generation stage failed â€” anomalies persisted but unexplained")

# # def main():
# #     parser = argparse.ArgumentParser(description="Crypto anomaly-detection pipeline runner")
# #     group = parser.add_mutually_exclusive_group(required=True)
# #     group.add_argument("--single-run", action="store_true", help="Run one poll and exit")
# #     group.add_argument("--interval", type=int, help="Run continuously every N seconds")
# #     args = parser.parse_args()

# #     db.init_db(config.DB_PATH)

# #     if args.single_run:
# #         run_once()
# #     else:
# #         run_loop(args.interval)


# # if __name__ == "__main__":
# #     main()
# """
# Pipeline orchestrator.

# Usage:
#     python pipeline_runner.py --single-run
#     python pipeline_runner.py --interval 60

# Error isolation: a failure in ingestion (e.g. both sources down), DB
# write, quality checks, anomaly detection, or narrative generation is
# caught and logged per-stage, not allowed to crash the loop. A bad poll
# should never take down future polls or lose already-written data â€”
# same principle as Module 1's original design, just now applied across
# five stages instead of one.
# """

# import argparse
# import logging
# import time
# from datetime import datetime, timezone

# import pipeline.config as config
# from pipeline.src import anomaly, db, ingest, narrative, quality
# from dotenv import load_dotenv
# load_dotenv()
# logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# log = logging.getLogger("pipeline_runner")


# def run_once() -> None:
#     recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
#     log.info("=== poll start: %s ===", recorded_at)

#     # --- Stage 1: ingestion (own try/except so a fetch failure
#     # doesn't prevent the DB layer or the next poll from running) ---
#     try:
#         fetch_start = time.perf_counter()
#         readings = ingest.fetch_all(recorded_at)
#         fetch_stage_ms = (time.perf_counter() - fetch_start) * 1000
#     except Exception:
#         log.exception("Ingestion stage failed entirely for this poll â€” skipping DB write")
#         return

#     if not readings:
#         log.warning("No readings collected this poll (all sources failed) â€” nothing to write")
#         return

#     # --- Stage 2: DB write (measured separately from fetch, per the
#     # Module 1 latency-profiling design â€” lets us say precisely where
#     # time is going, and whether failover polls are slower end-to-end) ---
#     try:
#         write_start = time.perf_counter()
#         inserted, skipped = db.insert_readings_batch(config.DB_PATH, readings)
#         write_stage_ms = (time.perf_counter() - write_start) * 1000
#     except Exception:
#         log.exception("DB write stage failed â€” readings collected but not persisted this poll")
#         return

#     failover_count = sum(1 for r in readings if r["is_failover"])
#     log.info(
#         "poll done: %d fetched, %d inserted, %d skipped (dup), %d via failover | "
#         "fetch_stage=%.1fms write_stage=%.1fms",
#         len(readings), inserted, skipped, failover_count, fetch_stage_ms, write_stage_ms,
#     )

#     # --- Stage 3: data quality checks (own try/except â€” a bug in a
#     # quality check should never take down ingestion; readings are
#     # already safely persisted by this point regardless of what
#     # Module 2 finds) ---
#     try:
#         quality_start = time.perf_counter()
#         flags = quality.run_all_checks(config.DB_PATH, recorded_at, readings)
#         quality_stage_ms = (time.perf_counter() - quality_start) * 1000
#         log.info(
#             "quality checks done: %d flag(s) raised | quality_stage=%.1fms",
#             len(flags), quality_stage_ms,
#         )
#     except Exception:
#         log.exception("Quality-check stage failed â€” this poll's data is persisted but unvalidated")

#     # --- Stage 4: anomaly detection (own try/except â€” same isolation
#     # principle as every prior stage; a bug here shouldn't undo the
#     # ingestion or quality-check work already done this poll).
#     #
#     # anomalies is initialized to [] *before* the try so that Stage 5
#     # below always has something safe to check, even if this stage
#     # raises partway through. ---
#     anomalies = []
#     try:
#         anomaly_start = time.perf_counter()
#         anomalies = anomaly.run_all_checks(config.DB_PATH, recorded_at, readings)
#         anomaly_stage_ms = (time.perf_counter() - anomaly_start) * 1000
#         log.info(
#             "anomaly checks done: %d anomaly(ies) detected | anomaly_stage=%.1fms",
#             len(anomalies), anomaly_stage_ms,
#         )
#     except Exception:
#         log.exception("Anomaly-detection stage failed â€” this poll's data is persisted but not scored")

#     # --- Stage 5: narrative generation (own try/except â€” same isolation
#     # principle as every prior stage; an LLM failure shouldn't lose the
#     # anomaly data already persisted).
#     #
#     # Fix note: this stage previously sat outside run_once() entirely
#     # (dedented to module scope after run_loop's def), so it never ran
#     # as part of a poll and referenced an `anomalies` name that didn't
#     # exist in that scope. It now runs in-sequence right after Stage 4,
#     # inside run_once(), guarded by `if anomalies:` so a clean poll
#     # (the common case) skips the LLM call entirely. ---
#     if anomalies:
#         try:
#             narrative_start = time.perf_counter()
#             narratives = narrative.attach_history_and_generate(config.DB_PATH, anomalies)
#             narrative_stage_ms = (time.perf_counter() - narrative_start) * 1000
#             log.info(
#                 "narrative generation done: %d narrative(s) | narrative_stage=%.1fms",
#                 len(narratives), narrative_stage_ms,
#             )
#         except Exception:
#             log.exception("Narrative-generation stage failed â€” anomalies persisted but unexplained")


# def run_loop(interval_seconds: int) -> None:
#     log.info("Starting continuous polling every %ds (Ctrl+C to stop)", interval_seconds)
#     try:
#         while True:
#             run_once()
#             time.sleep(interval_seconds)
#     except KeyboardInterrupt:
#         log.info("Stopped by user")


# def main():
#     parser = argparse.ArgumentParser(description="Crypto anomaly-detection pipeline runner")
#     group = parser.add_mutually_exclusive_group(required=True)
#     group.add_argument("--single-run", action="store_true", help="Run one poll and exit")
#     group.add_argument("--interval", type=int, help="Run continuously every N seconds")
#     args = parser.parse_args()

#     db.init_db(config.DB_PATH)

#     if args.single_run:
#         run_once()
#     else:
#         run_loop(args.interval)


# if __name__ == "__main__":
#     main()
"""
Pipeline orchestrator.

Usage:
    python pipeline_runner.py --single-run
    python pipeline_runner.py --interval 60

Error isolation: a failure in ingestion (e.g. both sources down), DB
write, quality checks, anomaly detection, or narrative generation is
caught and logged per-stage, not allowed to crash the loop. A bad poll
should never take down future polls or lose already-written data â€”
same principle as Module 1's original design, just now applied across
five stages instead of one.
"""

import argparse
import logging
import time
from datetime import datetime, timezone

from dotenv import load_dotenv

load_dotenv()  # must run before `from pipeline.src import narrative` below â€” narrative.py
                # builds the Groq client at import time and needs GROQ_API_KEY
                # already loaded into the environment by then

import pipeline.config as config
from pipeline.src import anomaly, db, ingest, narrative, quality

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("pipeline_runner")


def run_once() -> None:
    recorded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log.info("=== poll start: %s ===", recorded_at)

    # --- Stage 1: ingestion (own try/except so a fetch failure
    # doesn't prevent the DB layer or the next poll from running) ---
    try:
        fetch_start = time.perf_counter()
        readings = ingest.fetch_all(recorded_at)
        fetch_stage_ms = (time.perf_counter() - fetch_start) * 1000
    except Exception:
        log.exception("Ingestion stage failed entirely for this poll â€” skipping DB write")
        return

    if not readings:
        log.warning("No readings collected this poll (all sources failed) â€” nothing to write")
        return

    # --- Stage 2: DB write (measured separately from fetch, per the
    # Module 1 latency-profiling design â€” lets us say precisely where
    # time is going, and whether failover polls are slower end-to-end) ---
    try:
        write_start = time.perf_counter()
        inserted, skipped = db.insert_readings_batch(config.DB_PATH, readings)
        write_stage_ms = (time.perf_counter() - write_start) * 1000
    except Exception:
        log.exception("DB write stage failed â€” readings collected but not persisted this poll")
        return

    failover_count = sum(1 for r in readings if r["is_failover"])
    log.info(
        "poll done: %d fetched, %d inserted, %d skipped (dup), %d via failover | "
        "fetch_stage=%.1fms write_stage=%.1fms",
        len(readings), inserted, skipped, failover_count, fetch_stage_ms, write_stage_ms,
    )

    # --- Stage 3: data quality checks (own try/except â€” a bug in a
    # quality check should never take down ingestion; readings are
    # already safely persisted by this point regardless of what
    # Module 2 finds) ---
    try:
        quality_start = time.perf_counter()
        flags = quality.run_all_checks(config.DB_PATH, recorded_at, readings)
        quality_stage_ms = (time.perf_counter() - quality_start) * 1000
        log.info(
            "quality checks done: %d flag(s) raised | quality_stage=%.1fms",
            len(flags), quality_stage_ms,
        )
    except Exception:
        log.exception("Quality-check stage failed â€” this poll's data is persisted but unvalidated")

    # --- Stage 4: anomaly detection (own try/except â€” same isolation
    # principle as every prior stage; a bug here shouldn't undo the
    # ingestion or quality-check work already done this poll).
    #
    # anomalies is initialized to [] *before* the try so that Stage 5
    # below always has something safe to check, even if this stage
    # raises partway through. ---
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
        log.exception("Anomaly-detection stage failed â€” this poll's data is persisted but not scored")

    # --- Stage 5: narrative generation (own try/except â€” same isolation
    # principle as every prior stage; an LLM failure shouldn't lose the
    # anomaly data already persisted).
    #
    # Fix note: this stage previously sat outside run_once() entirely
    # (dedented to module scope after run_loop's def), so it never ran
    # as part of a poll and referenced an `anomalies` name that didn't
    # exist in that scope. It now runs in-sequence right after Stage 4,
    # inside run_once(), guarded by `if anomalies:` so a clean poll
    # (the common case) skips the LLM call entirely. ---
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
            log.exception("Narrative-generation stage failed â€” anomalies persisted but unexplained")


def run_loop(interval_seconds: int) -> None:
    log.info("Starting continuous polling every %ds (Ctrl+C to stop)", interval_seconds)
    try:
        while True:
            run_once()
            time.sleep(interval_seconds)
    except KeyboardInterrupt:
        log.info("Stopped by user")


def main():
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
