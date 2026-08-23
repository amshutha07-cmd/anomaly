# # """
# # Persistence layer.

# # Idempotency design: UNIQUE(recorded_at, asset_id, source) + INSERT OR
# # IGNORE. recorded_at is bucketed to the poll timestamp (not raw
# # wall-clock at insert time), so re-running the same poll — or a retry
# # after a partial failure — never creates duplicate rows. This avoids a
# # manual check-then-insert, which has a race condition under concurrent
# # pollers.

# # source is part of the unique key (not just asset_id) because we now
# # store readings from two independent sources per poll — that's what
# # makes cross-source reconciliation in Module 2 possible.
# # """

# # import sqlite3
# # from contextlib import contextmanager

# # SCHEMA = """
# # CREATE TABLE IF NOT EXISTS crypto_prices (
# #     id              INTEGER PRIMARY KEY AUTOINCREMENT,
# #     recorded_at     TEXT    NOT NULL,   -- ISO8601, bucketed to poll time
# #     asset_id        TEXT    NOT NULL,   -- e.g. 'bitcoin'
# #     source          TEXT    NOT NULL,   -- 'coingecko' | 'binance'
# #     price_usd       REAL    NOT NULL,
# #     volume_24h_usd  REAL,
# #     market_cap_usd  REAL,
# #     is_failover      INTEGER NOT NULL DEFAULT 0,  -- 1 if primary failed and this came from secondary
# #     fetch_latency_ms REAL,
# #     inserted_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
# #     UNIQUE(recorded_at, asset_id, source)
# # );

# # CREATE INDEX IF NOT EXISTS idx_crypto_prices_recorded_at
# #     ON crypto_prices(recorded_at);

# # CREATE INDEX IF NOT EXISTS idx_crypto_prices_asset_time
# #     ON crypto_prices(asset_id, recorded_at);

# # -- Module 2: data quality / pipeline integrity.
# # -- One row per check that fired (not per poll) — a clean poll produces
# # -- zero rows here. check_type distinguishes the check that fired, e.g.
# # -- 'cross_source_divergence', 'null_field', 'gap', 'schema_invalid'.
# # -- severity lets reconciliation flags (warning-level, price still usable)
# # -- be told apart from harder failures (error-level, data untrustworthy).
# # CREATE TABLE IF NOT EXISTS quality_flags (
# #     id           INTEGER PRIMARY KEY AUTOINCREMENT,
# #     recorded_at  TEXT    NOT NULL,
# #     asset_id     TEXT,                 -- NULL for pipeline-wide flags (e.g. a gap)
# #     check_type   TEXT    NOT NULL,
# #     severity     TEXT    NOT NULL,     -- 'warning' | 'error'
# #     detail       TEXT,                 -- human-readable specifics, e.g. "divergence 0.41% > 0.32% threshold"
# #     created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
# # );

# # CREATE INDEX IF NOT EXISTS idx_quality_flags_recorded_at
# #     ON quality_flags(recorded_at);
# # """


# # @contextmanager
# # def get_conn(db_path: str):
# #     conn = sqlite3.connect(db_path)
# #     conn.execute("PRAGMA journal_mode=WAL;")
# #     try:
# #         yield conn
# #     finally:
# #         conn.close()


# # def init_db(db_path: str) -> None:
# #     with get_conn(db_path) as conn:
# #         conn.executescript(SCHEMA)
# #         conn.commit()


# # def insert_reading(db_path: str, reading: dict) -> bool:
# #     """
# #     Insert one price reading in its own connection. Returns True if a
# #     new row was inserted, False if it was a duplicate and was silently
# #     ignored. Kept for single-row/ad-hoc use (e.g. quick manual tests);
# #     batch writes should use insert_readings_batch instead — see its
# #     docstring for why.
# #     """
# #     with get_conn(db_path) as conn:
# #         cur = conn.execute(
# #             """
# #             INSERT OR IGNORE INTO crypto_prices
# #                 (recorded_at, asset_id, source, price_usd,
# #                  volume_24h_usd, market_cap_usd, is_failover, fetch_latency_ms)
# #             VALUES (:recorded_at, :asset_id, :source, :price_usd,
# #                     :volume_24h_usd, :market_cap_usd, :is_failover, :fetch_latency_ms)
# #             """,
# #             reading,
# #         )
# #         conn.commit()
# #         return cur.rowcount == 1


# # def insert_readings_batch(db_path: str, readings: list[dict]) -> tuple[int, int]:
# #     """
# #     Insert many readings in ONE connection and ONE transaction.

# #     Fix note: this previously called insert_reading() in a loop, which
# #     opened and closed a brand-new SQLite connection per row — meaning a
# #     5-reading poll did 5 separate connect/WAL-sync/close cycles. That
# #     was the leading suspect for the write-stage latency spikes observed
# #     during Module 2 testing (376–734ms on some polls vs. 60–113ms on
# #     others, with identical row counts each time — connection overhead,
# #     not data volume, was the variable). Batching into a single
# #     transaction removes that per-row overhead entirely.
# #     """
# #     inserted = 0
# #     skipped = 0
# #     with get_conn(db_path) as conn:
# #         for r in readings:
# #             cur = conn.execute(
# #                 """
# #                 INSERT OR IGNORE INTO crypto_prices
# #                     (recorded_at, asset_id, source, price_usd,
# #                      volume_24h_usd, market_cap_usd, is_failover, fetch_latency_ms)
# #                 VALUES (:recorded_at, :asset_id, :source, :price_usd,
# #                         :volume_24h_usd, :market_cap_usd, :is_failover, :fetch_latency_ms)
# #                 """,
# #                 r,
# #             )
# #             if cur.rowcount == 1:
# #                 inserted += 1
# #             else:
# #                 skipped += 1
# #         conn.commit()
# #     return inserted, skipped


# # def latest_readings(db_path: str, asset_id: str, limit: int = 5) -> list[tuple]:
# #     """Quick sanity-check query: most recent rows for one asset."""
# #     with get_conn(db_path) as conn:
# #         cur = conn.execute(
# #             """
# #             SELECT recorded_at, source, price_usd, is_failover
# #             FROM crypto_prices
# #             WHERE asset_id = ?
# #             ORDER BY recorded_at DESC
# #             LIMIT ?
# #             """,
# #             (asset_id, limit),
# #         )
# #         return cur.fetchall()


# # def readings_for_poll(db_path: str, recorded_at: str) -> list[dict]:
# #     """All rows written for one specific poll timestamp — what quality.py checks against."""
# #     with get_conn(db_path) as conn:
# #         conn.row_factory = sqlite3.Row
# #         cur = conn.execute(
# #             """
# #             SELECT asset_id, source, price_usd, volume_24h_usd, market_cap_usd, is_failover
# #             FROM crypto_prices
# #             WHERE recorded_at = ?
# #             """,
# #             (recorded_at,),
# #         )
# #         return [dict(row) for row in cur.fetchall()]


# # def insert_quality_flag(db_path: str, flag: dict) -> None:
# #     """Record one quality-check failure. No dedup needed — each poll's checks are independent."""
# #     with get_conn(db_path) as conn:
# #         conn.execute(
# #             """
# #             INSERT INTO quality_flags (recorded_at, asset_id, check_type, severity, detail)
# #             VALUES (:recorded_at, :asset_id, :check_type, :severity, :detail)
# #             """,
# #             flag,
# #         )
# #         conn.commit()


# # def recent_quality_flags(db_path: str, limit: int = 20) -> list[tuple]:
# #     """Sanity-check query: most recent quality flags across all checks."""
# #     with get_conn(db_path) as conn:
# #         cur = conn.execute(
# #             """
# #             SELECT recorded_at, asset_id, check_type, severity, detail
# #             FROM quality_flags
# #             ORDER BY recorded_at DESC
# #             LIMIT ?
# #             """,
# #             (limit,),
# #         )
# #         return cur.fetchall()


# # def last_recorded_at_before(db_path: str, recorded_at: str) -> str | None:
# #     """Previous poll's timestamp — used by the gap check to measure actual vs. expected spacing."""
# #     with get_conn(db_path) as conn:
# #         cur = conn.execute(
# #             """
# #             SELECT DISTINCT recorded_at FROM crypto_prices
# #             WHERE recorded_at < ?
# #             ORDER BY recorded_at DESC
# #             LIMIT 1
# #             """,
# #             (recorded_at,),
# #         )
# #         row = cur.fetchone()
# #         return row[0] if row else None
# """
# Persistence layer.

# Idempotency design: UNIQUE(recorded_at, asset_id, source) + INSERT OR
# IGNORE. recorded_at is bucketed to the poll timestamp (not raw
# wall-clock at insert time), so re-running the same poll — or a retry
# after a partial failure — never creates duplicate rows. This avoids a
# manual check-then-insert, which has a race condition under concurrent
# pollers.

# source is part of the unique key (not just asset_id) because we now
# store readings from two independent sources per poll — that's what
# makes cross-source reconciliation in Module 2 possible.
# """

# import sqlite3
# from contextlib import contextmanager

# SCHEMA = """
# CREATE TABLE IF NOT EXISTS crypto_prices (
#     id              INTEGER PRIMARY KEY AUTOINCREMENT,
#     recorded_at     TEXT    NOT NULL,   -- ISO8601, bucketed to poll time
#     asset_id        TEXT    NOT NULL,   -- e.g. 'bitcoin'
#     source          TEXT    NOT NULL,   -- 'coingecko' | 'binance'
#     price_usd       REAL    NOT NULL,
#     volume_24h_usd  REAL,
#     market_cap_usd  REAL,
#     is_failover      INTEGER NOT NULL DEFAULT 0,  -- 1 if primary failed and this came from secondary
#     fetch_latency_ms REAL,
#     inserted_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
#     UNIQUE(recorded_at, asset_id, source)
# );

# CREATE INDEX IF NOT EXISTS idx_crypto_prices_recorded_at
#     ON crypto_prices(recorded_at);

# CREATE INDEX IF NOT EXISTS idx_crypto_prices_asset_time
#     ON crypto_prices(asset_id, recorded_at);

# -- Module 2: data quality / pipeline integrity.
# -- One row per check that fired (not per poll) — a clean poll produces
# -- zero rows here. check_type distinguishes the check that fired, e.g.
# -- 'cross_source_divergence', 'null_field', 'gap', 'schema_invalid'.
# -- severity lets reconciliation flags (warning-level, price still usable)
# -- be told apart from harder failures (error-level, data untrustworthy).
# CREATE TABLE IF NOT EXISTS quality_flags (
#     id           INTEGER PRIMARY KEY AUTOINCREMENT,
#     recorded_at  TEXT    NOT NULL,
#     asset_id     TEXT,                 -- NULL for pipeline-wide flags (e.g. a gap)
#     check_type   TEXT    NOT NULL,
#     severity     TEXT    NOT NULL,     -- 'warning' | 'error'
#     detail       TEXT,                 -- human-readable specifics, e.g. "divergence 0.41% > 0.32% threshold"
#     created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
# );

# CREATE INDEX IF NOT EXISTS idx_quality_flags_recorded_at
#     ON quality_flags(recorded_at);

# -- Module 3: anomaly detection. One row per anomaly that fires.
# -- anomaly_type: 'zscore_price' | 'iqr_price' | 'zscore_volume' | 'peg_deviation'.
# -- reference_value/threshold_used are stored (not just a boolean) so a
# -- flagged anomaly can be explained without recomputing stats later —
# -- this is also what Module 4 will hand to the LLM for narrative context.
# CREATE TABLE IF NOT EXISTS anomalies (
#     id              INTEGER PRIMARY KEY AUTOINCREMENT,
#     recorded_at     TEXT    NOT NULL,
#     asset_id        TEXT    NOT NULL,
#     anomaly_type    TEXT    NOT NULL,
#     observed_value  REAL,             -- e.g. the current return %, or current USDT price
#     reference_value REAL,             -- e.g. historical mean return, or $1.00 for peg
#     score           REAL,             -- e.g. the z-score, or IQR distance, or peg deviation %
#     threshold_used  REAL,
#     detail          TEXT,
#     created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
# );

# CREATE INDEX IF NOT EXISTS idx_anomalies_recorded_at
#     ON anomalies(recorded_at);
# """


# @contextmanager
# def get_conn(db_path: str):
#     conn = sqlite3.connect(db_path)
#     conn.execute("PRAGMA journal_mode=WAL;")
#     try:
#         yield conn
#     finally:
#         conn.close()


# def init_db(db_path: str) -> None:
#     with get_conn(db_path) as conn:
#         conn.executescript(SCHEMA)
#         conn.commit()


# def insert_reading(db_path: str, reading: dict) -> bool:
#     """
#     Insert one price reading in its own connection. Returns True if a
#     new row was inserted, False if it was a duplicate and was silently
#     ignored. Kept for single-row/ad-hoc use (e.g. quick manual tests);
#     batch writes should use insert_readings_batch instead — see its
#     docstring for why.
#     """
#     with get_conn(db_path) as conn:
#         cur = conn.execute(
#             """
#             INSERT OR IGNORE INTO crypto_prices
#                 (recorded_at, asset_id, source, price_usd,
#                  volume_24h_usd, market_cap_usd, is_failover, fetch_latency_ms)
#             VALUES (:recorded_at, :asset_id, :source, :price_usd,
#                     :volume_24h_usd, :market_cap_usd, :is_failover, :fetch_latency_ms)
#             """,
#             reading,
#         )
#         conn.commit()
#         return cur.rowcount == 1


# def insert_readings_batch(db_path: str, readings: list[dict]) -> tuple[int, int]:
#     """
#     Insert many readings in ONE connection and ONE transaction.

#     Fix note: this previously called insert_reading() in a loop, which
#     opened and closed a brand-new SQLite connection per row — meaning a
#     5-reading poll did 5 separate connect/WAL-sync/close cycles. That
#     was the leading suspect for the write-stage latency spikes observed
#     during Module 2 testing (376–734ms on some polls vs. 60–113ms on
#     others, with identical row counts each time — connection overhead,
#     not data volume, was the variable). Batching into a single
#     transaction removes that per-row overhead entirely.
#     """
#     inserted = 0
#     skipped = 0
#     with get_conn(db_path) as conn:
#         for r in readings:
#             cur = conn.execute(
#                 """
#                 INSERT OR IGNORE INTO crypto_prices
#                     (recorded_at, asset_id, source, price_usd,
#                      volume_24h_usd, market_cap_usd, is_failover, fetch_latency_ms)
#                 VALUES (:recorded_at, :asset_id, :source, :price_usd,
#                         :volume_24h_usd, :market_cap_usd, :is_failover, :fetch_latency_ms)
#                 """,
#                 r,
#             )
#             if cur.rowcount == 1:
#                 inserted += 1
#             else:
#                 skipped += 1
#         conn.commit()
#     return inserted, skipped


# def latest_readings(db_path: str, asset_id: str, limit: int = 5) -> list[tuple]:
#     """Quick sanity-check query: most recent rows for one asset."""
#     with get_conn(db_path) as conn:
#         cur = conn.execute(
#             """
#             SELECT recorded_at, source, price_usd, is_failover
#             FROM crypto_prices
#             WHERE asset_id = ?
#             ORDER BY recorded_at DESC
#             LIMIT ?
#             """,
#             (asset_id, limit),
#         )
#         return cur.fetchall()


# def readings_for_poll(db_path: str, recorded_at: str) -> list[dict]:
#     """All rows written for one specific poll timestamp — what quality.py checks against."""
#     with get_conn(db_path) as conn:
#         conn.row_factory = sqlite3.Row
#         cur = conn.execute(
#             """
#             SELECT asset_id, source, price_usd, volume_24h_usd, market_cap_usd, is_failover
#             FROM crypto_prices
#             WHERE recorded_at = ?
#             """,
#             (recorded_at,),
#         )
#         return [dict(row) for row in cur.fetchall()]


# def insert_quality_flag(db_path: str, flag: dict) -> None:
#     """Record one quality-check failure. No dedup needed — each poll's checks are independent."""
#     with get_conn(db_path) as conn:
#         conn.execute(
#             """
#             INSERT INTO quality_flags (recorded_at, asset_id, check_type, severity, detail)
#             VALUES (:recorded_at, :asset_id, :check_type, :severity, :detail)
#             """,
#             flag,
#         )
#         conn.commit()


# def recent_quality_flags(db_path: str, limit: int = 20) -> list[tuple]:
#     """Sanity-check query: most recent quality flags across all checks."""
#     with get_conn(db_path) as conn:
#         cur = conn.execute(
#             """
#             SELECT recorded_at, asset_id, check_type, severity, detail
#             FROM quality_flags
#             ORDER BY recorded_at DESC
#             LIMIT ?
#             """,
#             (limit,),
#         )
#         return cur.fetchall()


# def last_recorded_at_before(db_path: str, recorded_at: str) -> str | None:
#     """Previous poll's timestamp — used by the gap check to measure actual vs. expected spacing."""
#     with get_conn(db_path) as conn:
#         cur = conn.execute(
#             """
#             SELECT DISTINCT recorded_at FROM crypto_prices
#             WHERE recorded_at < ?
#             ORDER BY recorded_at DESC
#             LIMIT 1
#             """,
#             (recorded_at,),
#         )
#         row = cur.fetchone()
#         return row[0] if row else None


# def price_history(db_path: str, asset_id: str, source: str, before: str, limit: int) -> list[tuple]:
#     """
#     Historical (recorded_at, price_usd, volume_24h_usd) for one asset,
#     strictly before `before`, most recent first, capped at `limit`.

#     source is pinned to a single canonical source (coingecko) rather
#     than mixing both — mixing CoinGecko and Binance readings into one
#     return-series would inject the ~0.05-0.07% cross-source gap
#     (Module 2) into the anomaly stats as noise, which would understate
#     real anomalies. Reconciliation (Module 2) and anomaly detection
#     (Module 3) intentionally use the data differently for this reason.
#     """
#     with get_conn(db_path) as conn:
#         cur = conn.execute(
#             """
#             SELECT recorded_at, price_usd, volume_24h_usd
#             FROM crypto_prices
#             WHERE asset_id = ? AND source = ? AND recorded_at < ?
#             ORDER BY recorded_at DESC
#             LIMIT ?
#             """,
#             (asset_id, source, before, limit),
#         )
#         return cur.fetchall()


# def insert_anomaly(db_path: str, anomaly: dict) -> None:
#     with get_conn(db_path) as conn:
#         conn.execute(
#             """
#             INSERT INTO anomalies
#                 (recorded_at, asset_id, anomaly_type, observed_value,
#                  reference_value, score, threshold_used, detail)
#             VALUES (:recorded_at, :asset_id, :anomaly_type, :observed_value,
#                     :reference_value, :score, :threshold_used, :detail)
#             """,
#             anomaly,
#         )
#         conn.commit()


# def recent_anomalies(db_path: str, limit: int = 20) -> list[tuple]:
#     with get_conn(db_path) as conn:
#         cur = conn.execute(
#             """
#             SELECT recorded_at, asset_id, anomaly_type, observed_value, score, detail
#             FROM anomalies
#             ORDER BY recorded_at DESC
#             LIMIT ?
#             """,
#             (limit,),
#         )
#         return cur.fetchall()
# def init_narratives_table(conn):
#     conn.execute("""
#         CREATE TABLE IF NOT EXISTS narratives (
#             anomaly_id INTEGER PRIMARY KEY,
#             severity TEXT,
#             likely_cause TEXT,
#             recommended_action TEXT,
#             narrative TEXT
#         )
#     """)

# def insert_narrative(db_path: str, n: dict):
#     conn = sqlite3.connect(db_path)
#     try:
#         conn.execute(
#             "INSERT OR REPLACE INTO narratives "
#             "(anomaly_id, severity, likely_cause, recommended_action, narrative) "
#             "VALUES (?, ?, ?, ?, ?)",
#             (n["anomaly_id"], n["severity"], n["likely_cause"],
#              n["recommended_action"], n["narrative"]),
#         )
#         conn.commit()
#     finally:
#         conn.close()
"""
Persistence layer.

Idempotency design: UNIQUE(recorded_at, asset_id, source) + INSERT OR
IGNORE. recorded_at is bucketed to the poll timestamp (not raw
wall-clock at insert time), so re-running the same poll — or a retry
after a partial failure — never creates duplicate rows. This avoids a
manual check-then-insert, which has a race condition under concurrent
pollers.

source is part of the unique key (not just asset_id) because we now
store readings from two independent sources per poll — that's what
makes cross-source reconciliation in Module 2 possible.
"""

import sqlite3
from contextlib import contextmanager

SCHEMA = """
CREATE TABLE IF NOT EXISTS crypto_prices (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at     TEXT    NOT NULL,   -- ISO8601, bucketed to poll time
    asset_id        TEXT    NOT NULL,   -- e.g. 'bitcoin'
    source          TEXT    NOT NULL,   -- 'coingecko' | 'binance'
    price_usd       REAL    NOT NULL,
    volume_24h_usd  REAL,
    market_cap_usd  REAL,
    is_failover      INTEGER NOT NULL DEFAULT 0,  -- 1 if primary failed and this came from secondary
    fetch_latency_ms REAL,
    inserted_at     TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(recorded_at, asset_id, source)
);

CREATE INDEX IF NOT EXISTS idx_crypto_prices_recorded_at
    ON crypto_prices(recorded_at);

CREATE INDEX IF NOT EXISTS idx_crypto_prices_asset_time
    ON crypto_prices(asset_id, recorded_at);

-- Module 2: data quality / pipeline integrity.
-- One row per check that fired (not per poll) — a clean poll produces
-- zero rows here. check_type distinguishes the check that fired, e.g.
-- 'cross_source_divergence', 'null_field', 'gap', 'schema_invalid'.
-- severity lets reconciliation flags (warning-level, price still usable)
-- be told apart from harder failures (error-level, data untrustworthy).
CREATE TABLE IF NOT EXISTS quality_flags (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at  TEXT    NOT NULL,
    asset_id     TEXT,                 -- NULL for pipeline-wide flags (e.g. a gap)
    check_type   TEXT    NOT NULL,
    severity     TEXT    NOT NULL,     -- 'warning' | 'error'
    detail       TEXT,                 -- human-readable specifics, e.g. "divergence 0.41% > 0.32% threshold"
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_quality_flags_recorded_at
    ON quality_flags(recorded_at);

-- Module 3: anomaly detection. One row per anomaly that fires.
-- anomaly_type: 'zscore_price' | 'iqr_price' | 'zscore_volume' | 'peg_deviation'.
-- reference_value/threshold_used are stored (not just a boolean) so a
-- flagged anomaly can be explained without recomputing stats later —
-- this is also what Module 4 hands to the LLM for narrative context.
CREATE TABLE IF NOT EXISTS anomalies (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    recorded_at     TEXT    NOT NULL,
    asset_id        TEXT    NOT NULL,
    anomaly_type    TEXT    NOT NULL,
    observed_value  REAL,             -- e.g. the current return %, or current USDT price
    reference_value REAL,             -- e.g. historical mean return, or $1.00 for peg
    score           REAL,             -- e.g. the z-score, or IQR distance, or peg deviation %
    threshold_used  REAL,
    detail          TEXT,
    created_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);

CREATE INDEX IF NOT EXISTS idx_anomalies_recorded_at
    ON anomalies(recorded_at);

-- Module 4: AI-generated narrative per anomaly. One row per anomaly_id
-- (PRIMARY KEY, not AUTOINCREMENT id) — an anomaly gets at most one
-- narrative; INSERT OR REPLACE lets a re-run overwrite rather than
-- duplicate.
CREATE TABLE IF NOT EXISTS narratives (
    anomaly_id          INTEGER PRIMARY KEY,
    severity             TEXT,
    likely_cause         TEXT,
    recommended_action   TEXT,
    narrative            TEXT,
    provider_used        TEXT,
    model_used           TEXT,
    latency_ms           REAL,
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    fallback_used        INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (anomaly_id) REFERENCES anomalies(id)
);
"""


@contextmanager
def get_conn(db_path: str):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
    finally:
        conn.close()


def init_db(db_path: str) -> None:
    with get_conn(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


def insert_reading(db_path: str, reading: dict) -> bool:
    """
    Insert one price reading in its own connection. Returns True if a
    new row was inserted, False if it was a duplicate and was silently
    ignored. Kept for single-row/ad-hoc use (e.g. quick manual tests);
    batch writes should use insert_readings_batch instead — see its
    docstring for why.
    """
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO crypto_prices
                (recorded_at, asset_id, source, price_usd,
                 volume_24h_usd, market_cap_usd, is_failover, fetch_latency_ms)
            VALUES (:recorded_at, :asset_id, :source, :price_usd,
                    :volume_24h_usd, :market_cap_usd, :is_failover, :fetch_latency_ms)
            """,
            reading,
        )
        conn.commit()
        return cur.rowcount == 1


def insert_readings_batch(db_path: str, readings: list[dict]) -> tuple[int, int]:
    """
    Insert many readings in ONE connection and ONE transaction.

    Fix note: this previously called insert_reading() in a loop, which
    opened and closed a brand-new SQLite connection per row — meaning a
    5-reading poll did 5 separate connect/WAL-sync/close cycles. That
    was the leading suspect for the write-stage latency spikes observed
    during Module 2 testing (376–734ms on some polls vs. 60–113ms on
    others, with identical row counts each time — connection overhead,
    not data volume, was the variable). Batching into a single
    transaction removes that per-row overhead entirely.
    """
    inserted = 0
    skipped = 0
    with get_conn(db_path) as conn:
        for r in readings:
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO crypto_prices
                    (recorded_at, asset_id, source, price_usd,
                     volume_24h_usd, market_cap_usd, is_failover, fetch_latency_ms)
                VALUES (:recorded_at, :asset_id, :source, :price_usd,
                        :volume_24h_usd, :market_cap_usd, :is_failover, :fetch_latency_ms)
                """,
                r,
            )
            if cur.rowcount == 1:
                inserted += 1
            else:
                skipped += 1
        conn.commit()
    return inserted, skipped


def latest_readings(db_path: str, asset_id: str, limit: int = 5) -> list[tuple]:
    """Quick sanity-check query: most recent rows for one asset."""
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT recorded_at, source, price_usd, is_failover
            FROM crypto_prices
            WHERE asset_id = ?
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (asset_id, limit),
        )
        return cur.fetchall()


def readings_for_poll(db_path: str, recorded_at: str) -> list[dict]:
    """All rows written for one specific poll timestamp — what quality.py checks against."""
    with get_conn(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            """
            SELECT asset_id, source, price_usd, volume_24h_usd, market_cap_usd, is_failover
            FROM crypto_prices
            WHERE recorded_at = ?
            """,
            (recorded_at,),
        )
        return [dict(row) for row in cur.fetchall()]


def insert_quality_flag(db_path: str, flag: dict) -> None:
    """Record one quality-check failure. No dedup needed — each poll's checks are independent."""
    with get_conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO quality_flags (recorded_at, asset_id, check_type, severity, detail)
            VALUES (:recorded_at, :asset_id, :check_type, :severity, :detail)
            """,
            flag,
        )
        conn.commit()


def recent_quality_flags(db_path: str, limit: int = 20) -> list[tuple]:
    """Sanity-check query: most recent quality flags across all checks."""
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT recorded_at, asset_id, check_type, severity, detail
            FROM quality_flags
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


def last_recorded_at_before(db_path: str, recorded_at: str) -> str | None:
    """Previous poll's timestamp — used by the gap check to measure actual vs. expected spacing."""
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT DISTINCT recorded_at FROM crypto_prices
            WHERE recorded_at < ?
            ORDER BY recorded_at DESC
            LIMIT 1
            """,
            (recorded_at,),
        )
        row = cur.fetchone()
        return row[0] if row else None


def price_history(db_path: str, asset_id: str, source: str, before: str, limit: int) -> list[tuple]:
    """
    Historical (recorded_at, price_usd, volume_24h_usd) for one asset,
    strictly before `before`, most recent first, capped at `limit`.

    source is pinned to a single canonical source (coingecko) rather
    than mixing both — mixing CoinGecko and Binance readings into one
    return-series would inject the ~0.05-0.07% cross-source gap
    (Module 2) into the anomaly stats as noise, which would understate
    real anomalies. Reconciliation (Module 2), anomaly detection
    (Module 3), and narrative context (Module 4) all use this same
    canonical-source query for that reason — the LLM sees exactly the
    data the anomaly check reasoned over, not a separately-sourced view.
    """
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT recorded_at, price_usd, volume_24h_usd
            FROM crypto_prices
            WHERE asset_id = ? AND source = ? AND recorded_at < ?
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (asset_id, source, before, limit),
        )
        return cur.fetchall()


def insert_anomaly(db_path: str, anomaly: dict) -> int:
    """
    Insert one anomaly and return its new row id (cursor.lastrowid).

    Fix note: this previously returned nothing, so the anomaly dicts
    passed around in memory never got the DB-assigned id attached to
    them. That id is exactly what Module 4's `narratives` table needs
    as its anomaly_id foreign key — see anomaly.run_all_checks, which
    now does `a["id"] = db.insert_anomaly(db_path, a)`.
    """
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO anomalies
                (recorded_at, asset_id, anomaly_type, observed_value,
                 reference_value, score, threshold_used, detail)
            VALUES (:recorded_at, :asset_id, :anomaly_type, :observed_value,
                    :reference_value, :score, :threshold_used, :detail)
            """,
            anomaly,
        )
        conn.commit()
        return cur.lastrowid


def recent_anomalies(db_path: str, limit: int = 20) -> list[tuple]:
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT recorded_at, asset_id, anomaly_type, observed_value, score, detail
            FROM anomalies
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


def insert_narrative(db_path: str, n: dict) -> None:
    """
    Persist one narrative, keyed by anomaly_id. INSERT OR REPLACE so
    re-running narrative generation for the same anomaly (e.g. after a
    retry) overwrites rather than errors on the PRIMARY KEY.
    """
    with get_conn(db_path) as conn:
        conn.execute(
    """
    INSERT OR REPLACE INTO narratives
        (anomaly_id, severity, likely_cause, recommended_action, narrative,
         provider_used, model_used, latency_ms, prompt_tokens,
         completion_tokens, fallback_used)
    VALUES
        (:anomaly_id, :severity, :likely_cause, :recommended_action, :narrative,
         :provider_used, :model_used, :latency_ms, :prompt_tokens,
         :completion_tokens, :fallback_used)
    """,
    n,
)
        conn.commit()


def recent_narratives(db_path: str, limit: int = 20) -> list[tuple]:
    """Sanity-check query: most recent narratives, joined with their anomaly for context."""
    with get_conn(db_path) as conn:
        cur = conn.execute(
            """
            SELECT a.recorded_at, a.asset_id, a.anomaly_type, n.severity, n.narrative
            FROM narratives n
            JOIN anomalies a ON a.id = n.anomaly_id
            ORDER BY a.recorded_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()