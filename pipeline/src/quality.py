"""
Module 2 — Data Quality & Pipeline Integrity.

Centerpiece check is cross-source reconciliation: because Module 1
stores readings from two independent sources (CoinGecko + Binance) per
asset per poll, we can directly compare them. This is the
BitGo-relevant version of "data quality" — for a custody company, the
question isn't just "is this field null", it's "do two independent
sources agree this price is real."

Baseline checks (nulls, schema/sanity bounds, polling gaps) are kept
underneath the reconciliation check, per the original implementation
plan, but reconciliation is the check that actually earns its place —
it's the one that couldn't exist without the Module 1 dual-source design.
"""

import logging
from datetime import datetime, timezone

import pipeline.config as config
from pipeline.src import db

log = logging.getLogger("quality")


def check_nulls(readings: list[dict]) -> list[dict]:
    """Flag any reading missing a price — the one field nothing downstream can work without."""
    flags = []
    for r in readings:
        if r.get("price_usd") is None:
            flags.append({
                "asset_id": r.get("asset_id"),
                "check_type": "null_field",
                "severity": "error",
                "detail": f"price_usd is null (source={r.get('source')})",
            })
    return flags


def check_schema_sanity(readings: list[dict]) -> list[dict]:
    """Flag prices outside a sane bound — almost always a parsing bug, not a real market move."""
    flags = []
    for r in readings:
        price = r.get("price_usd")
        if price is None:
            continue  # already caught by check_nulls
        if not (config.PRICE_SANITY_MIN_USD <= price <= config.PRICE_SANITY_MAX_USD):
            flags.append({
                "asset_id": r.get("asset_id"),
                "check_type": "schema_invalid",
                "severity": "error",
                "detail": f"price_usd={price} outside sane bounds "
                          f"[{config.PRICE_SANITY_MIN_USD}, {config.PRICE_SANITY_MAX_USD}] "
                          f"(source={r.get('source')})",
            })
    return flags


def check_reconciliation(readings: list[dict]) -> list[dict]:
    """
    Compare CoinGecko vs. Binance price for the same asset in the same
    poll. Only fires when both sources actually reported (if one failed
    over, there's nothing to reconcile against — that's Module 1's
    failover logic, not a quality issue).
    """
    flags = []
    by_asset: dict[str, dict[str, float]] = {}
    for r in readings:
        by_asset.setdefault(r["asset_id"], {})[r["source"]] = r["price_usd"]

    for asset_id, by_source in by_asset.items():
        if "coingecko" not in by_source or "binance" not in by_source:
            continue  # only one source reported this poll — nothing to reconcile
        cg_price = by_source["coingecko"]
        bn_price = by_source["binance"]
        if not cg_price or not bn_price:
            continue
        divergence_pct = abs(cg_price - bn_price) / cg_price * 100

        if divergence_pct > config.RECONCILIATION_DIVERGENCE_THRESHOLD_PCT:
            flags.append({
                "asset_id": asset_id,
                "check_type": "cross_source_divergence",
                "severity": "warning",
                "detail": (
                    f"coingecko=${cg_price:.4f} vs binance=${bn_price:.4f} "
                    f"({divergence_pct:.3f}% divergence, threshold="
                    f"{config.RECONCILIATION_DIVERGENCE_THRESHOLD_PCT}%)"
                ),
            })
    return flags


def check_gap(db_path: str, recorded_at: str) -> list[dict]:
    """
    Flag if the previous poll was longer ago than expected — catches
    API downtime or a scheduler stall, not just a missing field.
    """
    prev = db.last_recorded_at_before(db_path, recorded_at)
    if prev is None:
        return []  # first poll ever, nothing to compare against

    try:
        current_dt = datetime.fromisoformat(recorded_at)
        prev_dt = datetime.fromisoformat(prev)
    except ValueError:
        return []  # malformed timestamp — not this check's job to fix

    gap_seconds = (current_dt - prev_dt).total_seconds()
    tolerance = config.POLL_INTERVAL_SECONDS * config.GAP_TOLERANCE_MULTIPLIER

    if gap_seconds > tolerance:
        return [{
            "asset_id": None,  # pipeline-wide, not asset-specific
            "check_type": "gap",
            "severity": "warning",
            "detail": (
                f"{gap_seconds:.0f}s since previous poll "
                f"(expected ~{config.POLL_INTERVAL_SECONDS}s, tolerance {tolerance:.0f}s)"
            ),
        }]
    return []


def run_all_checks(db_path: str, recorded_at: str, readings: list[dict]) -> list[dict]:
    """
    Run every Module 2 check for one poll and persist any flags that
    fire. Returns the flags (already written to quality_flags) so the
    caller can log a summary.
    """
    all_flags = []
    all_flags += check_nulls(readings)
    all_flags += check_schema_sanity(readings)
    all_flags += check_reconciliation(readings)
    all_flags += check_gap(db_path, recorded_at)

    for flag in all_flags:
        flag["recorded_at"] = recorded_at
        db.insert_quality_flag(db_path, flag)
        log_fn = log.error if flag["severity"] == "error" else log.warning
        log_fn("[%s] %s: %s", flag["check_type"], flag.get("asset_id") or "pipeline", flag["detail"])

    return all_flags