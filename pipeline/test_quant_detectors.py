import asyncio
import os
from pathlib import Path
import numpy as np

os.environ.setdefault("GROQ_API_KEY", "test-key-for-pytest")

import pipeline.config as config
from hosted.api.tools.sync_pipeline_to_supabase import warm_up_sqlite_from_supabase
from pipeline.quant_detectors import (
    FEATURE_COLUMNS,
    compute_meta_regime_probability,
    extract_regime_features,
    calibrate_rolling_threshold,
    detect_ewma_mad,
    detect_isolation_forest,
    detect_mahalanobis_regime,
)
from pipeline.src import anomaly, db, narrative


def test_ewma_mad_resists_variance_poisoning():
    rng = np.random.default_rng(7)
    series = list(rng.normal(0.0, 0.002, size=40))
    series.append(-0.08)
    series.append(0.001)
    series.append(-0.018)

    res = detect_ewma_mad(series, span=12, threshold=3.0)
    assert res["is_anomaly"] is True
    assert res["robust_z"] > 3.0


def test_mahalanobis_detects_correlation_breakdown_and_attributes_features():
    rng = np.random.default_rng(11)
    cov = np.array([[1.0, 0.9], [0.9, 1.0]]) * 0.001
    baseline = rng.multivariate_normal([0.0, 0.0], cov, size=45)
    shock = np.array([[0.08, -0.09]])
    matrix = np.vstack([baseline, shock])

    res = detect_mahalanobis_regime(matrix, feature_names=["btc_ret", "eth_ret"], threshold=3.0)
    assert res["is_anomaly"] is True
    assert abs(sum(res["feature_attribution_pct"].values()) - 100.0) < 0.1
    assert res["dominant_driver"] in ("btc_ret", "eth_ret")


def test_isolation_forest_flags_multivariate_outlier():
    rng = np.random.default_rng(21)
    normal = rng.normal(0.0, 0.002, size=(50, 3))
    outlier = np.array([[0.05, -0.05, 0.03]])
    matrix = np.vstack([normal, outlier])

    res = detect_isolation_forest(matrix, contamination=0.05)
    assert res["is_anomaly"] is True
    assert res["anomaly_score"] > 0.5


def test_live_pipeline_persists_ewma_and_mahalanobis_with_attribution(tmp_path: Path):
    rng = np.random.default_rng(99)
    db_path = str(tmp_path / "test_veyra.db")
    db.init_db(db_path)

    btc_price = 60000.0
    eth_price = 3000.0
    for i in range(16):
        ts = f"2026-11-18T00:{i:02d}:00Z"
        shared_move = float(rng.normal(0.0, 0.0015))
        btc_price *= (1.0 + shared_move)
        eth_price *= (1.0 + shared_move + float(rng.normal(0.0, 0.0002)))
        readings = [
            {
                "recorded_at": ts,
                "asset_id": "bitcoin",
                "source": config.ANOMALY_SOURCE,
                "price_usd": btc_price,
                "volume_24h_usd": 1e9,
                "market_cap_usd": 1e12,
                "is_failover": 0,
                "fetch_latency_ms": 12.0,
            },
            {
                "recorded_at": ts,
                "asset_id": "ethereum",
                "source": config.ANOMALY_SOURCE,
                "price_usd": eth_price,
                "volume_24h_usd": 5e8,
                "market_cap_usd": 4e11,
                "is_failover": 0,
                "fetch_latency_ms": 12.0,
            },
            {
                "recorded_at": ts,
                "asset_id": "tether",
                "source": config.ANOMALY_SOURCE,
                "price_usd": 1.0000,
                "volume_24h_usd": 2e9,
                "market_cap_usd": 1e11,
                "is_failover": 0,
                "fetch_latency_ms": 12.0,
            },
        ]
        db.insert_readings_batch(db_path, readings)

    shock_ts = "2026-11-18T00:16:00Z"
    shock_readings = [
        {
            "recorded_at": shock_ts,
            "asset_id": "bitcoin",
            "source": config.ANOMALY_SOURCE,
            "price_usd": btc_price * 1.025,
            "volume_24h_usd": 1e9,
            "market_cap_usd": 1e12,
            "is_failover": 0,
            "fetch_latency_ms": 15.0,
        },
        {
            "recorded_at": shock_ts,
            "asset_id": "ethereum",
            "source": config.ANOMALY_SOURCE,
            "price_usd": eth_price * 0.972,
            "volume_24h_usd": 5e8,
            "market_cap_usd": 4e11,
            "is_failover": 0,
            "fetch_latency_ms": 15.0,
        },
        {
            "recorded_at": shock_ts,
            "asset_id": "tether",
            "source": config.ANOMALY_SOURCE,
            "price_usd": 1.0001,
            "volume_24h_usd": 2e9,
            "market_cap_usd": 1e11,
            "is_failover": 0,
            "fetch_latency_ms": 15.0,
        },
    ]
    db.insert_readings_batch(db_path, shock_readings)

    detected = anomaly.run_all_checks(db_path, shock_ts, shock_readings)
    detected_types = {a["anomaly_type"] for a in detected}

    assert "ewma_mad_price" in detected_types
    assert "mahalanobis_regime" in detected_types

    mahal_row = next(a for a in detected if a["anomaly_type"] == "mahalanobis_regime")
    assert "attribution=[" in mahal_row["detail"]
    assert mahal_row["id"] is not None

    enriched = [{**mahal_row, "history": []}]
    prompt_text = narrative._build_user_prompt(enriched)
    assert "Statistical Detail & Feature Attribution:" in prompt_text
    assert "attribution=[" in prompt_text


def test_stateless_warm_up_guard_skips_when_warm(tmp_path: Path):
    db_file = tmp_path / "warm.db"
    db.init_db(str(db_file))
    readings = [
        {
            "recorded_at": f"2026-11-18T01:{i:02d}:00Z",
            "asset_id": "bitcoin",
            "source": config.ANOMALY_SOURCE,
            "price_usd": 60000.0 + i,
            "volume_24h_usd": 1e9,
            "market_cap_usd": 1e12,
            "is_failover": 0,
            "fetch_latency_ms": 10.0,
        }
        for i in range(10)
    ]
    db.insert_readings_batch(str(db_file), readings)
    seeded = asyncio.run(warm_up_sqlite_from_supabase(db_file, min_readings_per_asset=8))
    assert seeded == 0


def test_online_rolling_threshold_calibration():
    rng = np.random.default_rng(123)
    normal_scores = list(np.abs(rng.normal(0.8, 0.4, size=60)))
    normal_scores.append(25.0)
    calibrated = calibrate_rolling_threshold(normal_scores, floor_threshold=3.20, quantile=99.0, min_samples=30)
    assert 3.20 <= calibrated < 6.0


def test_supervised_feature_extraction_and_meta_probability():
    rng = np.random.default_rng(77)
    normal_win = rng.normal(0.0, 0.002, size=(48, 4))
    shock_row = np.array([[0.04, -0.045, 0.001, 0.45]])
    win_matrix = np.vstack([normal_win, shock_row])

    feats = extract_regime_features(win_matrix)
    assert feats.shape == (len(FEATURE_COLUMNS),)

    meta = compute_meta_regime_probability(win_matrix)
    assert 0.5 < meta["meta_probability"] <= 1.0
    assert meta["vol_expansion_ratio"] > 1.0


def test_sync_script_direct_invocation_has_no_import_error():
    import subprocess
    import sys
    res = subprocess.run(
        [sys.executable, "hosted/api/tools/sync_pipeline_to_supabase.py", "--dry-run"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert "ModuleNotFoundError" not in res.stderr
