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
