from __future__ import annotations
from typing import Any
import numpy as np
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import IsolationForest


def detect_ewma_mad(
    returns: list[float] | np.ndarray,
    span: int = 16,
    threshold: float = 3.0,
    huber_k: float = 1.5,
    eps: float = 1e-9,
) -> dict[str, Any]:
    """
    Univariate robust anomaly detector using Huberized Exponentially Weighted Moving Average (EWMA)
    expectations and Median Absolute Deviation (MAD) scaling to prevent both variance poisoning
    and post-crash mean drag.
    """
    arr = np.asarray(returns, dtype=float)
    if arr.size < 8:
        return {
            "is_anomaly": False,
            "robust_z": 0.0,
            "ewma_expected": 0.0,
            "mad_scale": 0.0,
            "latest_return": float(arr[-1]) if arr.size > 0 else 0.0,
        }

    baseline = arr[:-1]
    med_base = float(np.median(baseline))
    raw_mad = float(np.median(np.abs(baseline - med_base)))
    mad_scale = max(1.4826 * raw_mad, eps)

    alpha = 2.0 / (span + 1.0)
    ewma = np.zeros_like(arr)
    ewma[0] = med_base
    clip_bound = huber_k * mad_scale

    # Huberized state update: bound innovations so flash crashes do not drag EWMA level
    for i in range(1, len(arr)):
        innovation = arr[i] - ewma[i - 1]
        clipped_innovation = float(np.clip(innovation, -clip_bound, clip_bound))
        ewma[i] = ewma[i - 1] + alpha * clipped_innovation

    baseline_residuals = arr[1:-1] - ewma[:-2]
    med_res = float(np.median(baseline_residuals))
    res_mad = float(np.median(np.abs(baseline_residuals - med_res)))
    robust_scale = max(1.4826 * res_mad, eps)

    expected_now = float(ewma[-2])
    latest_val = float(arr[-1])
    current_residual = latest_val - expected_now
    robust_z = float(abs(current_residual - med_res) / robust_scale)

    return {
        "is_anomaly": bool(robust_z >= threshold),
        "robust_z": round(robust_z, 4),
        "ewma_expected": round(expected_now, 6),
        "mad_scale": round(robust_scale, 6),
        "latest_return": round(latest_val, 6),
    }


def detect_mahalanobis_regime(
    feature_matrix: np.ndarray,
    feature_names: list[str] | None = None,
    threshold: float = 3.2,
) -> dict[str, Any]:
    """
    Multivariate cross-asset regime detector using Ledoit-Wolf shrinkage covariance.
    Computes exact per-feature attribution percentages to ground LLM narratives.
    """
    X = np.asarray(feature_matrix, dtype=float)
    n_samples, n_features = X.shape
    if feature_names is None:
        feature_names = [f"feature_{i}" for i in range(n_features)]

    if n_samples < n_features + 5:
        return {
            "is_anomaly": False,
            "mahalanobis_distance": 0.0,
            "dominant_driver": None,
            "feature_attribution_pct": {k: 0.0 for k in feature_names},
        }

    baseline = X[:-1]
    current = X[-1]

    lw = LedoitWolf().fit(baseline)
    diff = current - lw.location_
    precision = lw.precision_

    weighted_diff = precision @ diff
    raw_contrib = np.abs(diff * weighted_diff)
    d_squared = float(np.max([0.0, float(diff.T @ weighted_diff)]))
    mahal_dist = float(np.sqrt(d_squared))

    total_contrib = float(np.sum(raw_contrib))
    if total_contrib > 1e-12:
        contrib_pct = (raw_contrib / total_contrib) * 100.0
    else:
        contrib_pct = np.zeros(n_features)

    attribution = {
        name: round(float(pct), 2)
        for name, pct in zip(feature_names, contrib_pct)
    }
    dominant_driver = max(attribution, key=attribution.get) if attribution else None

    return {
        "is_anomaly": bool(mahal_dist >= threshold),
        "mahalanobis_distance": round(mahal_dist, 4),
        "dominant_driver": dominant_driver,
        "feature_attribution_pct": attribution,
    }


def detect_isolation_forest(
    feature_matrix: np.ndarray,
    contamination: float = 0.04,
    random_state: int = 42,
) -> dict[str, Any]:
    """
    Non-parametric multivariate Isolation Forest detector for joint return and basis outliers.
    """
    X = np.asarray(feature_matrix, dtype=float)
    if X.shape[0] < 15:
        return {
            "is_anomaly": False,
            "anomaly_score": 0.0,
            "decision_margin": 0.0,
        }

    clf = IsolationForest(
        n_estimators=100,
        contamination=contamination,
        random_state=random_state,
    )
    preds = clf.fit_predict(X)
    raw_scores = -clf.score_samples(X)
    decision_vals = clf.decision_function(X)

    return {
        "is_anomaly": bool(preds[-1] == -1),
        "anomaly_score": round(float(raw_scores[-1]), 4),
        "decision_margin": round(float(decision_vals[-1]), 4),
    }
