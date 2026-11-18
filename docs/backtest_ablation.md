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
