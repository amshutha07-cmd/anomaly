"""
Config for Veyra: Quantitative Digital-Asset Anomaly & Regime Monitoring Platform.
Assets are keyed by CoinGecko id, with a Binance symbol as the failover mapping.
"""

ASSETS = {
    "bitcoin": {"binance_symbol": "BTCUSDT", "label": "BTC"},
    "ethereum": {"binance_symbol": "ETHUSDT", "label": "ETH"},
    "tether": {"binance_symbol": "USDTUSDT", "label": "USDT", "is_stablecoin": True},
}

COINGECKO_URL = "[https://api.coingecko.com/api/v3/simple/price](https://api.coingecko.com/api/v3/simple/price)"
BINANCE_TICKER_URL = "[https://api.binance.com/api/v3/ticker/24hr](https://api.binance.com/api/v3/ticker/24hr)"

POLL_INTERVAL_SECONDS = 60
MAX_RETRIES = 3
BACKOFF_BASE = 1.5
REQUEST_TIMEOUT_SECONDS = 8

DB_PATH = "pipeline/data/pipeline_data.db"

SOURCE_DIVERGENCE_WARN_PCT = 0.5
RECONCILIATION_DIVERGENCE_THRESHOLD_PCT = 0.5
GAP_TOLERANCE_MULTIPLIER = 2.0
PRICE_SANITY_MIN_USD = 0.0001
PRICE_SANITY_MAX_USD = 10_000_000

ANOMALY_SOURCE = "coingecko"
ANOMALY_WINDOW_SIZE = 96     # 24-hour rolling window at 15-minute polling intervals
ANOMALY_MIN_HISTORY = 8
ZSCORE_THRESHOLD = 3.00
IQR_MULTIPLIER = 1.5
PEG_TARGET_USD = 1.00
PEG_DEVIATION_THRESHOLD_PCT = 0.5

# Veyra 2.0 Calibrated Quantitative & Multivariate Regime Parameters
EWMA_SPAN = 16
EWMA_MAD_THRESHOLD = 3.20
EWMA_HUBER_K = 1.5
MAHALANOBIS_THRESHOLD = 4.06
IFOREST_CONTAMINATION = 0.04
ONLINE_QUANTILE_CALIBRATION = True
ONLINE_CALIBRATION_QUANTILE = 99.0

NARRATIVE_MODEL = "openai/gpt-oss-120b"
