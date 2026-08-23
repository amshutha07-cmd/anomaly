# """
# Module 3 — Anomaly Detection Logic.

# Two anomaly classes:

# 1. Statistical (z-score + IQR) on PERIOD-OVER-PERIOD RETURNS, not raw
#    price. Z-scoring raw price is a common mistake: price trends over
#    time, so a raw-price z-score would eventually flag almost every
#    reading as the price drifts away from its historical mean, even with
#    zero anomalous behavior. Returns (% change poll-to-poll) are
#    stationary in a way raw price isn't, which is why this is the
#    standard approach for financial anomaly detection, not just a
#    simplification.

# 2. USDT peg deviation — distance from $1.00. This is the
#    domain-specific anomaly class USDT was added to the asset set for
#    back in Module 1: a real, well-known, explainable anomaly type
#    (stablecoin depeg) rather than only a synthetic statistical trigger.

# Both checks require a minimum amount of history before they'll flag
# anything — see config.ANOMALY_MIN_HISTORY. Below that, mean/std (or
# quartiles) are themselves noise, and flagging on them would be
# indistinguishable from flagging on nothing.
# """

# import logging
# import statistics

# import pipeline.config
# from pipeline.src import db

# log = logging.getLogger("anomaly")


# def _compute_returns(prices_oldest_first: list[float]) -> list[float]:
#     """Period-over-period % returns from a price series (oldest first)."""
#     returns = []
#     for prev, curr in zip(prices_oldest_first, prices_oldest_first[1:]):
#         if prev:
#             returns.append((curr - prev) / prev * 100)
#     return returns


# def check_price_return_anomaly(db_path: str, recorded_at: str, asset_id: str, current_price: float) -> list[dict]:
#     """
#     Z-score AND IQR check on this poll's return vs. the historical
#     return distribution for this asset. Both methods are run (not just
#     one) because they catch slightly different things: z-score assumes
#     roughly normal returns and is sensitive to a single large outlier
#     pulling the mean; IQR is distribution-free and more robust to
#     existing outliers already in the window. Reporting both, even when
#     they agree, is more defensible than picking one and hoping.
#     """
#     history = db.price_history(db_path, asset_id, config.ANOMALY_SOURCE, recorded_at, config.ANOMALY_WINDOW_SIZE)
#     if len(history) < config.ANOMALY_MIN_HISTORY + 1:
#         log.info(
#             "[%s] insufficient history for return anomaly check (%d/%d polls) — skipping",
#             asset_id, len(history), config.ANOMALY_MIN_HISTORY + 1,
#         )
#         return []

#     prices_oldest_first = [row[1] for row in reversed(history)]
#     historical_returns = _compute_returns(prices_oldest_first)
#     if len(historical_returns) < config.ANOMALY_MIN_HISTORY:
#         return []

#     last_price = prices_oldest_first[-1]
#     if not last_price:
#         return []
#     current_return = (current_price - last_price) / last_price * 100

#     flags = []

#     # --- Z-score ---
#     mean_r = statistics.mean(historical_returns)
#     stdev_r = statistics.pstdev(historical_returns)
#     if stdev_r > 0:
#         z = (current_return - mean_r) / stdev_r
#         if abs(z) > config.ZSCORE_THRESHOLD:
#             flags.append({
#                 "recorded_at": recorded_at,
#                 "asset_id": asset_id,
#                 "anomaly_type": "zscore_price",
#                 "observed_value": current_return,
#                 "reference_value": mean_r,
#                 "score": z,
#                 "threshold_used": config.ZSCORE_THRESHOLD,
#                 "detail": f"return={current_return:.3f}% z={z:.2f} (mean={mean_r:.3f}%, stdev={stdev_r:.3f}%, n={len(historical_returns)})",
#             })

#     # --- IQR (Tukey's fences) ---
#     sorted_r = sorted(historical_returns)
#     q1 = statistics.median(sorted_r[:len(sorted_r) // 2]) if len(sorted_r) >= 4 else sorted_r[0]
#     q3 = statistics.median(sorted_r[(len(sorted_r) + 1) // 2:]) if len(sorted_r) >= 4 else sorted_r[-1]
#     iqr = q3 - q1
#     lower = q1 - config.IQR_MULTIPLIER * iqr
#     upper = q3 + config.IQR_MULTIPLIER * iqr
#     if iqr > 0 and not (lower <= current_return <= upper):
#         flags.append({
#             "recorded_at": recorded_at,
#             "asset_id": asset_id,
#             "anomaly_type": "iqr_price",
#             "observed_value": current_return,
#             "reference_value": (q1 + q3) / 2,
#             "score": iqr,
#             "threshold_used": config.IQR_MULTIPLIER,
#             "detail": f"return={current_return:.3f}% outside [{lower:.3f}%, {upper:.3f}%] (Q1={q1:.3f}%, Q3={q3:.3f}%, IQR={iqr:.3f}%)",
#         })

#     return flags


# def check_peg_deviation(recorded_at: str, readings: list[dict]) -> list[dict]:
#     """
#     USDT distance from $1.00. Unlike the statistical checks, this needs
#     no history — the reference point ($1.00) is fixed by definition of
#     what a stablecoin is, not derived from past data.
#     """
#     flags = []
#     for r in readings:
#         if r["asset_id"] != "tether" or r["source"] != config.ANOMALY_SOURCE:
#             continue
#         price = r.get("price_usd")
#         if price is None:
#             continue
#         deviation_pct = abs(price - config.PEG_TARGET_USD) / config.PEG_TARGET_USD * 100
#         log.info(
#             "[peg_deviation] USDT=$%.4f, %.4f%% from $1.00 peg (threshold=%.2f%%)",
#             price, deviation_pct, config.PEG_DEVIATION_THRESHOLD_PCT,
#         )
#         if deviation_pct > config.PEG_DEVIATION_THRESHOLD_PCT:
        
#             flags.append({
#                 "recorded_at": recorded_at,
#                 "asset_id": "tether",
#                 "anomaly_type": "peg_deviation",
#                 "observed_value": price,
#                 "reference_value": config.PEG_TARGET_USD,
#                 "score": deviation_pct,
#                 "threshold_used": config.PEG_DEVIATION_THRESHOLD_PCT,
#                 "detail": f"USDT=${price:.4f}, {deviation_pct:.3f}% from $1.00 peg (threshold={config.PEG_DEVIATION_THRESHOLD_PCT}%)",
#             })
#     return flags


# def run_all_checks(db_path: str, recorded_at: str, readings: list[dict]) -> list[dict]:
#     """
#     Run every Module 3 check for one poll and persist any anomalies
#     that fire. Returns the anomalies (already written to the
#     `anomalies` table) so the caller can log a summary.
#     """
#     all_anomalies = []

#     # Price return anomalies — one check per asset, using only the
#     # canonical-source reading for that asset this poll (see
#     # db.price_history's docstring for why sources aren't mixed).
#     for r in readings:
#         if r["source"] != config.ANOMALY_SOURCE or r.get("price_usd") is None:
#             continue
#         all_anomalies += check_price_return_anomaly(db_path, recorded_at, r["asset_id"], r["price_usd"])

#     all_anomalies += check_peg_deviation(recorded_at, readings)

#     for a in all_anomalies:
#         db.insert_anomaly(db_path, a)
#         log.warning("[%s] %s: %s", a["anomaly_type"], a["asset_id"], a["detail"])

#     return all_anomalies
"""
Module 3 — Anomaly Detection Logic.

Two anomaly classes:

1. Statistical (z-score + IQR) on PERIOD-OVER-PERIOD RETURNS, not raw
   price. Z-scoring raw price is a common mistake: price trends over
   time, so a raw-price z-score would eventually flag almost every
   reading as the price drifts away from its historical mean, even with
   zero anomalous behavior. Returns (% change poll-to-poll) are
   stationary in a way raw price isn't, which is why this is the
   standard approach for financial anomaly detection, not just a
   simplification.

2. USDT peg deviation — distance from $1.00. This is the
   domain-specific anomaly class USDT was added to the asset set for
   back in Module 1: a real, well-known, explainable anomaly type
   (stablecoin depeg) rather than only a synthetic statistical trigger.

Both checks require a minimum amount of history before they'll flag
anything — see config.ANOMALY_MIN_HISTORY. Below that, mean/std (or
quartiles) are themselves noise, and flagging on them would be
indistinguishable from flagging on nothing.
"""

import logging
import statistics

import pipeline.config
from pipeline.src import db

log = logging.getLogger("anomaly")


def _compute_returns(prices_oldest_first: list[float]) -> list[float]:
    """Period-over-period % returns from a price series (oldest first)."""
    returns = []
    for prev, curr in zip(prices_oldest_first, prices_oldest_first[1:]):
        if prev:
            returns.append((curr - prev) / prev * 100)
    return returns


def check_price_return_anomaly(db_path: str, recorded_at: str, asset_id: str, current_price: float) -> list[dict]:
    """
    Z-score AND IQR check on this poll's return vs. the historical
    return distribution for this asset. Both methods are run (not just
    one) because they catch slightly different things: z-score assumes
    roughly normal returns and is sensitive to a single large outlier
    pulling the mean; IQR is distribution-free and more robust to
    existing outliers already in the window. Reporting both, even when
    they agree, is more defensible than picking one and hoping.
    """
    history = db.price_history(db_path, asset_id, config.ANOMALY_SOURCE, recorded_at, config.ANOMALY_WINDOW_SIZE)
    if len(history) < config.ANOMALY_MIN_HISTORY + 1:
        log.info(
            "[%s] insufficient history for return anomaly check (%d/%d polls) — skipping",
            asset_id, len(history), config.ANOMALY_MIN_HISTORY + 1,
        )
        return []

    prices_oldest_first = [row[1] for row in reversed(history)]
    historical_returns = _compute_returns(prices_oldest_first)
    if len(historical_returns) < config.ANOMALY_MIN_HISTORY:
        return []

    last_price = prices_oldest_first[-1]
    if not last_price:
        return []
    current_return = (current_price - last_price) / last_price * 100

    flags = []

    # --- Z-score ---
    mean_r = statistics.mean(historical_returns)
    stdev_r = statistics.pstdev(historical_returns)
    if stdev_r > 0:
        z = (current_return - mean_r) / stdev_r
        if abs(z) > config.ZSCORE_THRESHOLD:
            flags.append({
                "recorded_at": recorded_at,
                "asset_id": asset_id,
                "anomaly_type": "zscore_price",
                "observed_value": current_return,
                "reference_value": mean_r,
                "score": z,
                "threshold_used": config.ZSCORE_THRESHOLD,
                "detail": f"return={current_return:.3f}% z={z:.2f} (mean={mean_r:.3f}%, stdev={stdev_r:.3f}%, n={len(historical_returns)})",
            })

    # --- IQR (Tukey's fences) ---
    sorted_r = sorted(historical_returns)
    q1 = statistics.median(sorted_r[:len(sorted_r) // 2]) if len(sorted_r) >= 4 else sorted_r[0]
    q3 = statistics.median(sorted_r[(len(sorted_r) + 1) // 2:]) if len(sorted_r) >= 4 else sorted_r[-1]
    iqr = q3 - q1
    lower = q1 - config.IQR_MULTIPLIER * iqr
    upper = q3 + config.IQR_MULTIPLIER * iqr
    if iqr > 0 and not (lower <= current_return <= upper):
        flags.append({
            "recorded_at": recorded_at,
            "asset_id": asset_id,
            "anomaly_type": "iqr_price",
            "observed_value": current_return,
            "reference_value": (q1 + q3) / 2,
            "score": iqr,
            "threshold_used": config.IQR_MULTIPLIER,
            "detail": f"return={current_return:.3f}% outside [{lower:.3f}%, {upper:.3f}%] (Q1={q1:.3f}%, Q3={q3:.3f}%, IQR={iqr:.3f}%)",
        })

    return flags


def check_peg_deviation(recorded_at: str, readings: list[dict]) -> list[dict]:
    """
    USDT distance from $1.00. Unlike the statistical checks, this needs
    no history — the reference point ($1.00) is fixed by definition of
    what a stablecoin is, not derived from past data.
    """
    flags = []
    for r in readings:
        if r["asset_id"] != "tether" or r["source"] != config.ANOMALY_SOURCE:
            continue
        price = r.get("price_usd")
        if price is None:
            continue
        deviation_pct = abs(price - config.PEG_TARGET_USD) / config.PEG_TARGET_USD * 100
        log.info(
            "[peg_deviation] USDT=$%.4f, %.4f%% from $1.00 peg (threshold=%.2f%%)",
            price, deviation_pct, config.PEG_DEVIATION_THRESHOLD_PCT,
        )
        if deviation_pct > config.PEG_DEVIATION_THRESHOLD_PCT:

            flags.append({
                "recorded_at": recorded_at,
                "asset_id": "tether",
                "anomaly_type": "peg_deviation",
                "observed_value": price,
                "reference_value": config.PEG_TARGET_USD,
                "score": deviation_pct,
                "threshold_used": config.PEG_DEVIATION_THRESHOLD_PCT,
                "detail": f"USDT=${price:.4f}, {deviation_pct:.3f}% from $1.00 peg (threshold={config.PEG_DEVIATION_THRESHOLD_PCT}%)",
            })
    return flags


def run_all_checks(db_path: str, recorded_at: str, readings: list[dict]) -> list[dict]:
    """
    Run every Module 3 check for one poll and persist any anomalies
    that fire. Returns the anomalies (already written to the
    `anomalies` table) so the caller can log a summary.

    Fix note: each anomaly dict now gets the DB-assigned row id
    attached as a["id"] right after insert. Previously insert_anomaly
    returned nothing, so downstream consumers (Module 4's
    narrative.py) had no anomaly_id to key the `narratives` table on.
    """
    all_anomalies = []

    # Price return anomalies — one check per asset, using only the
    # canonical-source reading for that asset this poll (see
    # db.price_history's docstring for why sources aren't mixed).
    for r in readings:
        if r["source"] != config.ANOMALY_SOURCE or r.get("price_usd") is None:
            continue
        all_anomalies += check_price_return_anomaly(db_path, recorded_at, r["asset_id"], r["price_usd"])

    all_anomalies += check_peg_deviation(recorded_at, readings)

    for a in all_anomalies:
        a["id"] = db.insert_anomaly(db_path, a)
        log.warning("[%s] %s: %s", a["anomaly_type"], a["asset_id"], a["detail"])

    return all_anomalies