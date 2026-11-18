"""
Config for Project 3: Real-Time Anomaly Detection Agent (crypto edition).
Design note: assets are keyed by CoinGecko id, with a Binance symbol as
the failover mapping. This lets ingest.py stay source-agnostic - adding
a new asset means adding one dict entry, not touching fetch logic.
"""

ASSETS = {
    "bitcoin": {"binance_symbol": "BTCUSDT", "label": "BTC"},
    "ethereum": {"binance_symbol": "ETHUSDT", "label": "ETH"},
    "tether": {"binance_symbol": "USDTUSDT", "label": "USDT", "is_stablecoin": True},
}

COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"

POLL_INTERVAL_SECONDS = 60
MAX_RETRIES = 3
BACKOFF_BASE = 1.5  # exponential backoff: BACKOFF_BASE ** attempt
REQUEST_TIMEOUT_SECONDS = 8

DB_PATH = "pipeline/data/pipeline_data.db"

SOURCE_DIVERGENCE_WARN_PCT = 0.5  # percent
RECONCILIATION_DIVERGENCE_THRESHOLD_PCT = 0.5
GAP_TOLERANCE_MULTIPLIER = 2.0  # e.g. 60s interval -> flag if gap > 120s
PRICE_SANITY_MIN_USD = 0.0001
PRICE_SANITY_MAX_USD = 10_000_000

ANOMALY_SOURCE = "coingecko"
ANOMALY_WINDOW_SIZE = 96
ANOMALY_MIN_HISTORY = 8
ZSCORE_THRESHOLD = 3.0       # standard choice: ~99.7% of normal-distributed returns fall within this
IQR_MULTIPLIER = 1.5         # standard Tukey's-fences multiplier
PEG_TARGET_USD = 1.00
PEG_DEVIATION_THRESHOLD_PCT = 0.5

# Veyra 2.0 Quantitative & Multivariate Regime Thresholds
EWMA_SPAN = 12
EWMA_MAD_THRESHOLD = 3.0
EWMA_HUBER_K = 2.5
MAHALANOBIS_THRESHOLD = 3.2
IFOREST_CONTAMINATION = 0.05

NARRATIVE_MODEL = "openai/gpt-oss-120b"
