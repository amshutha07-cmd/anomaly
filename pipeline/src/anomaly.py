"""
Module 3 - Anomaly Detection Logic (Veyra 2.0 Quantitative Suite).

Four anomaly tiers:
1. Classical Statistical (z-score + IQR) on period-over-period % returns.
2. Robust Adaptive Univariate (Huberized EWMA + MAD scaling) on period-over-period
   returns to prevent variance poisoning and post-crash mean drag.
3. Multivariate Cross-Asset Regime Detection (Ledoit-Wolf Shrinkage Mahalanobis
   Distance + Isolation Forest) across aligned [btc_return, eth_return, usdt_peg_dev]
   vectors with deterministic feature attribution percentages.
4. USDT stablecoin peg deviation from $1.00.
"""
import logging
import statistics
import numpy as np

import pipeline.config as config
from pipeline.quant_detectors import (
    calibrate_rolling_threshold,
    detect_ewma_mad,
    detect_isolation_forest,
    detect_mahalanobis_regime,
)
from pipeline.src import db

log = logging.getLogger("anomaly")


def _compute_returns(prices_oldest_first: list[float]) -> list[float]:
    """Period-over-period % returns from a price series (oldest first)."""
    returns = []
    for prev, curr in zip(prices_oldest_first, prices_oldest_first[1:]):
        if prev:
            returns.append((curr - prev) / prev * 100)
    return returns


def check_price_return_anomaly(
    db_path: str,
    recorded_at: str,
    asset_id: str,
    current_price: float,
) -> list[dict]:
    """
    Runs classical Z-score, Tukey IQR fences, and Huberized EWMA-MAD on this
    poll's return vs. the historical return distribution for this asset.
    """
    history = db.price_history(
        db_path,
        asset_id,
        config.ANOMALY_SOURCE,
        recorded_at,
        config.ANOMALY_WINDOW_SIZE,
    )
    if len(history) < config.ANOMALY_MIN_HISTORY + 1:
        log.info(
            "[%s] insufficient history for return anomaly check (%d/%d polls) - skipping",
            asset_id,
            len(history),
            config.ANOMALY_MIN_HISTORY + 1,
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

    # 1. Classical Parametric Z-Score
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
                "detail": (
                    f"return={current_return:.3f}% z={z:.2f} "
                    f"(mean={mean_r:.3f}%, stdev={stdev_r:.3f}%, n={len(historical_returns)})"
                ),
            })

    # 2. Non-Parametric Tukey IQR Fences
    sorted_r = sorted(historical_returns)
    q1 = statistics.median(sorted_r[: len(sorted_r) // 2]) if len(sorted_r) >= 4 else sorted_r[0]
    q3 = statistics.median(sorted_r[(len(sorted_r) + 1) // 2 :]) if len(sorted_r) >= 4 else sorted_r[-1]
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
            "detail": (
                f"return={current_return:.3f}% outside [{lower:.3f}%, {upper:.3f}%] "
                f"(Q1={q1:.3f}%, Q3={q3:.3f}%, IQR={iqr:.3f}%)"
            ),
        })

    # 3. Robust Adaptive Huberized EWMA-MAD (with online empirical quantile calibration)
    ewma_span = getattr(config, "EWMA_SPAN", 16)
    ewma_huber_k = getattr(config, "EWMA_HUBER_K", 1.5)
    ewma_floor = getattr(config, "EWMA_MAD_THRESHOLD", 3.20)
    if getattr(config, "ONLINE_QUANTILE_CALIBRATION", True) and len(historical_returns) >= 30:
        rolling_scores = [
            detect_ewma_mad(historical_returns[:k], span=ewma_span, threshold=ewma_floor, huber_k=ewma_huber_k)["robust_z"]
            for k in range(10, len(historical_returns) + 1)
        ]
        active_ewma_thresh = calibrate_rolling_threshold(
            rolling_scores,
            floor_threshold=ewma_floor,
            quantile=getattr(config, "ONLINE_CALIBRATION_QUANTILE", 99.0),
            min_samples=20,
        )
    else:
        active_ewma_thresh = ewma_floor

    series_with_current = historical_returns + [current_return]
    ewma_res = detect_ewma_mad(
        series_with_current,
        span=ewma_span,
        threshold=active_ewma_thresh,
        huber_k=ewma_huber_k,
    )
    if ewma_res["is_anomaly"]:
        flags.append({
            "recorded_at": recorded_at,
            "asset_id": asset_id,
            "anomaly_type": "ewma_mad_price",
            "observed_value": current_return,
            "reference_value": ewma_res["ewma_expected"],
            "score": ewma_res["robust_z"],
            "threshold_used": active_ewma_thresh,
            "detail": (
                f"return={current_return:.3f}% robust_z={ewma_res['robust_z']:.2f} "
                f"(ewma_expected={ewma_res['ewma_expected']:.3f}%, "
                f"mad_scale={ewma_res['mad_scale']:.3f}%, n={len(historical_returns)})"
            ),
        })

    return flags


def check_multivariate_regime(
    db_path: str,
    recorded_at: str,
    readings: list[dict],
) -> list[dict]:
    """
    Cross-asset multivariate regime detection across aligned BTC return, ETH return,
    and USDT peg deviation vectors using Ledoit-Wolf Shrinkage Mahalanobis Distance
    and Isolation Forest.
    """
    current_map = {
        r["asset_id"]: r["price_usd"]
        for r in readings
        if r.get("source") == config.ANOMALY_SOURCE and r.get("price_usd") is not None
    }
    if not all(k in current_map for k in ("bitcoin", "ethereum", "tether")):
        return []

    btc_hist = {
        row[0]: row[1]
        for row in db.price_history(
            db_path, "bitcoin", config.ANOMALY_SOURCE, recorded_at, config.ANOMALY_WINDOW_SIZE
        )
    }
    eth_hist = {
        row[0]: row[1]
        for row in db.price_history(
            db_path, "ethereum", config.ANOMALY_SOURCE, recorded_at, config.ANOMALY_WINDOW_SIZE
        )
    }
    usdt_hist = {
        row[0]: row[1]
        for row in db.price_history(
            db_path, "tether", config.ANOMALY_SOURCE, recorded_at, config.ANOMALY_WINDOW_SIZE
        )
    }

    common_ts = sorted(set(btc_hist) & set(eth_hist) & set(usdt_hist))
    if len(common_ts) < config.ANOMALY_MIN_HISTORY + 1:
        return []

    btc_prices = [btc_hist[t] for t in common_ts] + [current_map["bitcoin"]]
    eth_prices = [eth_hist[t] for t in common_ts] + [current_map["ethereum"]]
    usdt_prices = [usdt_hist[t] for t in common_ts] + [current_map["tether"]]

    btc_rets = _compute_returns(btc_prices)
    eth_rets = _compute_returns(eth_prices)
    usdt_devs = [
        (p - config.PEG_TARGET_USD) / config.PEG_TARGET_USD * 100.0
        for p in usdt_prices[1:]
    ]

    if len(btc_rets) < config.ANOMALY_MIN_HISTORY:
        return []

    binance_btc = {
        row[0]: row[1]
        for row in db.price_history(
            db_path, "bitcoin", "binance", recorded_at, config.ANOMALY_WINDOW_SIZE
        )
    }
    binance_now = next(
        (r["price_usd"] for r in readings if r.get("asset_id") == "bitcoin" and r.get("source") == "binance" and r.get("price_usd")),
        current_map["bitcoin"],
    )
    basis_series = []
    for t in common_ts[1:]:
        cg_p = btc_hist[t]
        bn_p = binance_btc.get(t, cg_p)
        basis_series.append(abs(cg_p - bn_p) / cg_p * 100.0 if cg_p else 0.0)
    cg_now = current_map["bitcoin"]
    basis_series.append(abs(cg_now - binance_now) / cg_now * 100.0 if cg_now else 0.0)

    feature_names = ["btc_return", "eth_return", "usdt_peg_dev", "exchange_basis"]
    matrix = np.column_stack([btc_rets, eth_rets, usdt_devs, basis_series])
    flags = []

    mahal_thresh = getattr(config, "MAHALANOBIS_THRESHOLD", 3.2)
    mahal_res = detect_mahalanobis_regime(
        matrix,
        feature_names=feature_names,
        threshold=mahal_thresh,
    )
    if mahal_res["is_anomaly"]:
        attr_str = ", ".join(
            f"{k}={v:.1f}%" for k, v in mahal_res["feature_attribution_pct"].items()
        )
        dominant = mahal_res["dominant_driver"] or "bitcoin"
        asset_map = {
            "btc_return": "bitcoin",
            "eth_return": "ethereum",
            "usdt_peg_dev": "tether",
        }
        primary_asset = asset_map.get(dominant, "bitcoin")
        obs_map = {
            "btc_return": btc_rets[-1],
            "eth_return": eth_rets[-1],
            "usdt_peg_dev": usdt_devs[-1],
            "exchange_basis": basis_series[-1],
        }

        flags.append({
            "recorded_at": recorded_at,
            "asset_id": primary_asset,
            "anomaly_type": "mahalanobis_regime",
            "observed_value": float(obs_map.get(dominant, btc_rets[-1])),
            "reference_value": 0.0,
            "score": mahal_res["mahalanobis_distance"],
            "threshold_used": mahal_thresh,
            "detail": (
                f"mahalanobis_d={mahal_res['mahalanobis_distance']:.2f} "
                f"dominant_driver={dominant} attribution=[{attr_str}] "
                f"(btc_ret={btc_rets[-1]:.3f}%, eth_ret={eth_rets[-1]:.3f}%, "
                f"usdt_dev={usdt_devs[-1]:.3f}%)"
            ),
        })

    if len(btc_rets) >= 15:
        iforest_contam = getattr(config, "IFOREST_CONTAMINATION", 0.05)
        iforest_res = detect_isolation_forest(matrix, contamination=iforest_contam)
        if iforest_res["is_anomaly"] and mahal_res["mahalanobis_distance"] >= (mahal_thresh * 0.85):
            flags.append({
                "recorded_at": recorded_at,
                "asset_id": "bitcoin",
                "anomaly_type": "isolation_forest_regime",
                "observed_value": float(btc_rets[-1]),
                "reference_value": 0.0,
                "score": iforest_res["anomaly_score"],
                "threshold_used": iforest_contam,
                "detail": (
                    f"iforest_score={iforest_res['anomaly_score']:.3f} "
                    f"margin={iforest_res['decision_margin']:.3f} "
                    f"(btc_ret={btc_rets[-1]:.3f}%, eth_ret={eth_rets[-1]:.3f}%, "
                    f"usdt_dev={usdt_devs[-1]:.3f}%)"
                ),
            })

    return flags


def check_peg_deviation(recorded_at: str, readings: list[dict]) -> list[dict]:
    """
    USDT distance from $1.00.
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
            price,
            deviation_pct,
            config.PEG_DEVIATION_THRESHOLD_PCT,
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
                "detail": (
                    f"USDT=${price:.4f}, {deviation_pct:.3f}% from $1.00 peg "
                    f"(threshold={config.PEG_DEVIATION_THRESHOLD_PCT}%)"
                ),
            })
    return flags


def run_all_checks(db_path: str, recorded_at: str, readings: list[dict]) -> list[dict]:
    """
    Run every Module 3 check (univariate + multivariate regime + stablecoin peg)
    for one poll and persist any anomalies that fire.
    """
    all_anomalies = []
    for r in readings:
        if r["source"] != config.ANOMALY_SOURCE or r.get("price_usd") is None:
            continue
        all_anomalies += check_price_return_anomaly(
            db_path, recorded_at, r["asset_id"], r["price_usd"]
        )

    all_anomalies += check_peg_deviation(recorded_at, readings)
    all_anomalies += check_multivariate_regime(db_path, recorded_at, readings)

    for a in all_anomalies:
        a["id"] = db.insert_anomaly(db_path, a)
        log.warning("[%s] %s: %s", a["anomaly_type"], a["asset_id"], a["detail"])

    return all_anomalies
