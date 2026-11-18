# Veyra ? Evidence-Led Digital-Asset Anomaly & Regime Monitoring

Veyra is a hosted quantitative crypto anomaly-detection, supervised meta-labeling, and alerting platform that turns multi-asset market observations into statistically attributed, auditable alerts. It polls **BTC, ETH, and USDT** prices from **CoinGecko and Binance** with automatic failover, validates cross-exchange data quality, and evaluates a 96-poll (24-hour) rolling window across an ensemble of **Huberized EWMA-MAD**, **4D Ledoit-Wolf Shrinkage Mahalanobis Distance**, **Isolation Forest**, and **Platt-Calibrated Supervised Meta-Labeling** over 10 engineered time-series features.

Only after a deterministic mathematical detector triggers does an LLM (**Groq**, with **OpenRouter** as automatic fallback) generate an operator triage narrative?grounded in exact quadratic-form **per-feature attribution percentages** (`[btc_return, eth_return, usdt_peg_dev, exchange_basis]`) and calibrated regime-shift probabilities (`meta_prob`) with strict JSON schema validation before persistence. Every alert is deduplicated via a deterministic idempotency key (`anomaly_id:alert_type:channel`), and every Slack webhook delivery attempt is logged for auditability.

**Live Demo:** https://anomaly-plum.vercel.app/ *(sign-in required)*

---

## Core Features

- **Resilient Multi-Source Ingestion:** Polls BTC, ETH, and USDT with automatic failover between CoinGecko and Binance and stateless **PostgreSQL-to-SQLite cold-start warm-up** for ephemeral CI runners.
- **Data-Quality & Basis Reconciliation:** Flags cross-source exchange price divergence (`> 0.5%`), schema anomalies, and polling gaps before statistical scoring.
- **Adaptive Univariate Detection (`ewma_mad_price`):** Huberized Exponentially Weighted Moving Average (`span=16`) with $\pm 1.5\,\hat{\sigma}_{\text{MAD}}$ innovation clipping, Median Absolute Deviation scaling ($1.4826 \cdot \text{MAD}$), and online 99th-percentile rolling threshold calibration to eliminate flash-crash variance poisoning and post-crash mean drag.
- **Multivariate Cross-Asset Regime Detection (`mahalanobis_regime` & `isolation_forest_regime`):** Fits a regularized **Ledoit-Wolf shrinkage precision matrix** ($\Sigma^{-1}$) and **Isolation Forest** over aligned 4D `[btc_return, eth_return, usdt_peg_dev, exchange_basis]` vectors to catch sub-$3\sigma$ BTC-ETH correlation breakdowns.
- **Supervised Meta-Labeling & Time-Series Feature Engineering (`d=10`):** Engineers rolling realized volatility expansion ($\sigma_8 / \sigma_{32}$), 16-period BTC-ETH correlation, return kurtosis, cross-asset spread, and exchange basis features; benchmarks L2 Logistic Regression, Random Forest, and Platt-Calibrated HistGradientBoosting across expanding Walk-Forward `TimeSeriesSplit` folds.
- **Attribution-Grounded AI Triage:** Computes exact quadratic-form feature attribution percentages from the Mahalanobis decomposition and passes them into Groq/OpenRouter prompts, validating JSON outputs before storage.
- **Idempotent Webhook State Machine:** Keyed by `anomaly_id:alert_type:channel` with bounded exponential-backoff retries and full state tracking (`pending` $\rightarrow$ `sending` $\rightarrow$ `sent` / `failed` $\rightarrow$ `acknowledged`).

---

## Architecture

| Stage | What Happens |
|---|---|
| **Warm-Up** | Backfill recent canonical readings from Supabase PostgreSQL into local SQLite if the CI cache is cold |
| **Ingest** | Fetch BTC, ETH, and USDT prices from CoinGecko and fail over to Binance on timeout or error |
| **Quality Checks** | Flag cross-exchange basis divergence (`> 0.5%`), sanity bounds, and polling gaps |
| **Quantitative & ML Detectors** | Run Huberized EWMA-MAD, 4D Ledoit-Wolf Mahalanobis, Isolation Forest, and 10-feature Supervised Meta-Probability scoring |
| **AI Narrative** | Ground Groq (or OpenRouter fallback) in historical windows, meta-probabilities, and exact feature attribution percentages |
| **Supabase Sync** | Upsert runs, canonical readings, quality flags, anomalies, and validated narratives to PostgreSQL |
| **Alert Dispatch** | Create idempotent alert intents (`anomaly_id:alert_type:channel`), deliver to Slack webhook with retries, and log every attempt |
| **Dashboard** | Display runs, findings, attribution details, narratives, alerts, and delivery logs in React + TypeScript |

---

# Veyra Out-of-Sample Backtest & Ablation Benchmark

- **Data Source:** Binance Live Historical 15m Klines (n=999 candles)
- **Calibration Split (0..499):** Matched 99.0th percentile false-alarm budget (`Z_thresh=3.00`, `EWMA_thresh=3.20`, `Mahal_thresh=4.06`)
- **Evaluation Split (500..998):** Held-out chronological test window (`window=64` polls, 25 stress events across flash-crash aftershocks & correlation breaks)

| Detector Architecture | Precision | Recall | F1-Score | AUC-PR |
|---|---|---|---|---|
| Legacy Rolling Z-Score | 1.000 | 0.200 | 0.333 | 0.665 |
| Huberized EWMA-MAD | 0.895 | 0.680 | 0.773 | 0.885 |
| Ledoit-Wolf Mahalanobis | 1.000 | 0.360 | 0.529 | 0.900 |
| Hybrid Ensemble (Veyra 2.0) | 0.913 | 0.840 | 0.875 | 0.946 |

## Supervised Meta-Labeling & Walk-Forward TimeSeriesSplit Benchmark (10 Engineered Features)

- **Validation Protocol:** 3-Fold Expanding Walk-Forward `TimeSeriesSplit` (zero future lookahead leakage)
- **Engineered Feature Space (`d=10`):** `btc_ewma_robust_z`, `eth_ewma_robust_z`, `mahalanobis_distance`, `vol_expansion_ratio_8_32`, `btc_eth_rolling_corr_16`, `cross_asset_return_spread`, `exchange_basis_spread`, `btc_rolling_kurtosis`, `btc_abs_return`, `eth_abs_return`

| Supervised Model (Walk-Forward OOF) | Precision | Recall | F1-Score | AUC-PR | ROC-AUC | Brier Score (?) |
|---|---|---|---|---|---|---|
| L2 Logistic Regression | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.0007 |
| Random Forest (100 Trees) | 0.909 | 1.000 | 0.952 | 1.000 | 1.000 | 0.0058 |
| Calibrated HistGradientBoosting (Meta-Labeler) | 0.889 | 0.800 | 0.842 | 0.932 | 0.994 | 0.0170 |

- **Top 5 Gini Feature Importances:** `btc_abs_return` (26.0%), `mahalanobis_distance` (18.6%), `btc_ewma_robust_z` (15.6%), `eth_abs_return` (12.0%), `eth_ewma_robust_z` (9.7%)

Reproduce both the unsupervised ablation and walk-forward supervised benchmark locally:
```powershell
python -m pipeline.evaluate_backtest
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| **Quantitative & ML Pipeline** | Python 3.11, NumPy, SciPy, Scikit-Learn (`LedoitWolf`, `IsolationForest`, `HistGradientBoostingClassifier`, `CalibratedClassifierCV`, `TimeSeriesSplit`) |
| **Backend API** | FastAPI, `asyncpg`, `PyJWT`, Uvicorn |
| **Databases** | SQLite (WAL local buffer), Supabase PostgreSQL (canonical store) |
| **Authentication** | Supabase Auth (JWT) |
| **Frontend Dashboard** | React, Vite, TypeScript, Tailwind CSS |
| **LLM Narrative Engine** | Groq (`openai/gpt-oss-120b`), OpenRouter (automatic failover) |
| **Alerting & Scheduling** | Slack Webhooks, GitHub Actions (15-minute cron + stateless warm-up) |
| **Testing** | `pytest` (25 unit, integration, and state-transition contract tests) |

---

## Quickstart

```powershell
git clone https://github.com/amshutha07-cmd/anomaly.git
cd anomaly

# 1. Backend & Quantitative Pipeline
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
copy .env.example .env

# Run unit tests & out-of-sample ablation + walk-forward supervised benchmark
python -m pytest -v
python -m pipeline.evaluate_backtest

# Start FastAPI server
cd hosted\api
python -m uvicorn app.main:app --port 8000 --env-file ..\..\.env

# 2. Frontend Dashboard (second terminal, from repo root)
cd hosted\dashboard
copy .env.example .env
pnpm install
pnpm exec vite
```

---

## Project Structure

```text
.
??? pipeline/                  # Ingestion, quality checks, quant + ML detectors, backtest benchmark, SQLite WAL layer
?   ??? quant_detectors.py     # Huberized EWMA-MAD, Ledoit-Wolf Mahalanobis, 10-feature extractor & meta-probability
?   ??? evaluate_backtest.py   # Real 15m Binance kline unsupervised ablation + 3-fold Walk-Forward TimeSeriesSplit suite
?   ??? test_quant_detectors.py# 25 unit & integration tests for statistical/ML detectors and warm-up guard
?   ??? src/                   # Core pipeline modules (ingest, quality, anomaly, narrative, db)
??? hosted/
?   ??? api/                   # FastAPI service, idempotent webhook dispatcher, Supabase sync & warm-up tools
?   ??? dashboard/             # React + Vite + TypeScript monitoring UI
??? .github/workflows/         # 15-minute scheduled monitoring workflow with cache + stateless warm-up
??? docs/                      # Architecture notes & generated ablation benchmark reports
??? requirements.txt           # Production Python dependencies
```

## License

MIT. See `LICENSE`.
