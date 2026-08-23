# # """
# # Config for Project 3: Real-Time Anomaly Detection Agent (crypto edition).

# # Design note: assets are keyed by CoinGecko id, with a Binance symbol as
# # the failover mapping. This lets ingest.py stay source-agnostic â€” adding
# # a new asset means adding one dict entry, not touching fetch logic.
# # """

# # # Asset universe. BTC + ETH are the "normal" high-liquidity assets.
# # # USDT (a stablecoin) is included deliberately: peg deviation is a
# # # real, well-known, explainable anomaly class (see USDT/USDC depeg
# # # events), which gives Module 3 a genuine anomaly to detect instead
# # # of a synthetic one.
# # ASSETS = {
# #     "bitcoin": {"binance_symbol": "BTCUSDT", "label": "BTC"},
# #     "ethereum": {"binance_symbol": "ETHUSDT", "label": "ETH"},
# #     "tether": {"binance_symbol": "USDTUSDT", "label": "USDT", "is_stablecoin": True},
# # }

# # # --- Source endpoints (both free, no API key required) ---
# # COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
# # BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"

# # # Note: Binance's ticker endpoint doesn't return a USD price for the
# # # USDTUSDT pair (it's always ~1 by definition, and Binance doesn't quote
# # # it against itself). For USDT, Binance failover uses USDT/BUSD or is
# # # skipped with a logged reason â€” see ingest.py's note on this.

# # # --- Scheduling / reliability knobs ---
# # POLL_INTERVAL_SECONDS = 60
# # MAX_RETRIES = 3
# # BACKOFF_BASE = 1.5  # exponential backoff: BACKOFF_BASE ** attempt
# # REQUEST_TIMEOUT_SECONDS = 8

# # # --- Storage ---
# # DB_PATH = "pipeline/data/pipeline_data.db"

# # # --- Cross-source reconciliation (used by Module 1 logging now,
# # # Module 2 quality checks later) ---
# # # If primary and secondary source prices for the same asset diverge by
# # # more than this fraction, it's worth flagging even at ingestion time.
# # SOURCE_DIVERGENCE_WARN_PCT = 0.5  # percent
# """
# Config for Project 3: Real-Time Anomaly Detection Agent (crypto edition).

# Design note: assets are keyed by CoinGecko id, with a Binance symbol as
# the failover mapping. This lets ingest.py stay source-agnostic â€” adding
# a new asset means adding one dict entry, not touching fetch logic.
# """

# # Asset universe. BTC + ETH are the "normal" high-liquidity assets.
# # USDT (a stablecoin) is included deliberately: peg deviation is a
# # real, well-known, explainable anomaly class (see USDT/USDC depeg
# # events), which gives Module 3 a genuine anomaly to detect instead
# # of a synthetic one.
# ASSETS = {
#     "bitcoin": {"binance_symbol": "BTCUSDT", "label": "BTC"},
#     "ethereum": {"binance_symbol": "ETHUSDT", "label": "ETH"},
#     "tether": {"binance_symbol": "USDTUSDT", "label": "USDT", "is_stablecoin": True},
# }

# # --- Source endpoints (both free, no API key required) ---
# COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
# BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"

# # Note: Binance's ticker endpoint doesn't return a USD price for the
# # USDTUSDT pair (it's always ~1 by definition, and Binance doesn't quote
# # it against itself). For USDT, Binance failover uses USDT/BUSD or is
# # skipped with a logged reason â€” see ingest.py's note on this.

# # --- Scheduling / reliability knobs ---
# POLL_INTERVAL_SECONDS = 60
# MAX_RETRIES = 3
# BACKOFF_BASE = 1.5  # exponential backoff: BACKOFF_BASE ** attempt
# REQUEST_TIMEOUT_SECONDS = 8

# # --- Storage ---
# DB_PATH = "pipeline/data/pipeline_data.db"

# # --- Cross-source reconciliation (used by Module 1 logging now,
# # Module 2 quality checks later) ---
# # If primary and secondary source prices for the same asset diverge by
# # more than this fraction, it's worth flagging even at ingestion time.
# SOURCE_DIVERGENCE_WARN_PCT = 0.5  # percent

# # --- Module 2: data quality thresholds ---
# # Starting point, not a guess: a live test run (Module 1) observed a
# # real ~0.32% CoinGecko-vs-Binance divergence on BTC under normal
# # conditions. Setting the flag threshold above that (0.5%) so normal
# # inter-exchange noise doesn't spam flags â€” only genuine divergence
# # (staleness, manipulation, an exchange-specific issue) should fire.
# # Revisit this once more live polls give a real distribution instead of
# # a single data point.
# RECONCILIATION_DIVERGENCE_THRESHOLD_PCT = 0.5 #0.02

# # A poll is "missing" if no rows exist for longer than this multiple of
# # the configured poll interval â€” catches API downtime / scheduler stalls
# # without false-flagging on ordinary small timing jitter between polls.
# GAP_TOLERANCE_MULTIPLIER = 2.0  # e.g. 60s interval -> flag if gap > 120s

# # Sanity bounds for schema validation â€” a price outside this range is
# # almost certainly a parsing bug or a corrupted API response, not a
# # real market move.
# PRICE_SANITY_MIN_USD = 0.0001
# PRICE_SANITY_MAX_USD = 10_000_000
"""
Config for Project 3: Real-Time Anomaly Detection Agent (crypto edition).

Design note: assets are keyed by CoinGecko id, with a Binance symbol as
the failover mapping. This lets ingest.py stay source-agnostic â€” adding
a new asset means adding one dict entry, not touching fetch logic.
"""

# Asset universe. BTC + ETH are the "normal" high-liquidity assets.
# USDT (a stablecoin) is included deliberately: peg deviation is a
# real, well-known, explainable anomaly class (see USDT/USDC depeg
# events), which gives Module 3 a genuine anomaly to detect instead
# of a synthetic one.
ASSETS = {
    "bitcoin": {"binance_symbol": "BTCUSDT", "label": "BTC"},
    "ethereum": {"binance_symbol": "ETHUSDT", "label": "ETH"},
    "tether": {"binance_symbol": "USDTUSDT", "label": "USDT", "is_stablecoin": True},
}

# --- Source endpoints (both free, no API key required) ---
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price"
BINANCE_TICKER_URL = "https://api.binance.com/api/v3/ticker/24hr"

# Note: Binance's ticker endpoint doesn't return a USD price for the
# USDTUSDT pair (it's always ~1 by definition, and Binance doesn't quote
# it against itself). For USDT, Binance failover uses USDT/BUSD or is
# skipped with a logged reason â€” see ingest.py's note on this.

# --- Scheduling / reliability knobs ---
POLL_INTERVAL_SECONDS = 60
MAX_RETRIES = 3
BACKOFF_BASE = 1.5  # exponential backoff: BACKOFF_BASE ** attempt
REQUEST_TIMEOUT_SECONDS = 8

# --- Storage ---
DB_PATH = "pipeline/data/pipeline_data.db"

# --- Cross-source reconciliation (used by Module 1 logging now,
# Module 2 quality checks later) ---
# If primary and secondary source prices for the same asset diverge by
# more than this fraction, it's worth flagging even at ingestion time.
SOURCE_DIVERGENCE_WARN_PCT = 0.5  # percent

# --- Module 2: data quality thresholds ---
# Starting point, not a guess: a live test run (Module 1) observed a
# real ~0.32% CoinGecko-vs-Binance divergence on BTC under normal
# conditions. Setting the flag threshold above that (0.5%) so normal
# inter-exchange noise doesn't spam flags â€” only genuine divergence
# (staleness, manipulation, an exchange-specific issue) should fire.
# Revisit this once more live polls give a real distribution instead of
# a single data point.
RECONCILIATION_DIVERGENCE_THRESHOLD_PCT = 0.5

# A poll is "missing" if no rows exist for longer than this multiple of
# the configured poll interval â€” catches API downtime / scheduler stalls
# without false-flagging on ordinary small timing jitter between polls.
GAP_TOLERANCE_MULTIPLIER = 2.0  # e.g. 60s interval -> flag if gap > 120s

# Sanity bounds for schema validation â€” a price outside this range is
# almost certainly a parsing bug or a corrupted API response, not a
# real market move.
PRICE_SANITY_MIN_USD = 0.0001
PRICE_SANITY_MAX_USD = 10_000_000

# --- Module 3: anomaly detection thresholds ---
# Canonical source for time-series stats (see db.price_history's
# docstring for why this must be a single source, not mixed).
ANOMALY_SOURCE = "coingecko"

# How many historical polls to compute rolling stats over.
ANOMALY_WINDOW_SIZE = 20

# Minimum historical RETURNS (i.e. window_size - 1 price points) needed
# before flagging anything. Below this, mean/std are themselves noise â€”
# better to log "insufficient history" than flag on a meaningless stat.
ANOMALY_MIN_HISTORY = 8

ZSCORE_THRESHOLD = 3.0 #0.5 #3.0       # standard choice: ~99.7% of normal-distributed returns fall within this
IQR_MULTIPLIER = 1.5         # standard Tukey's-fences multiplier

# USDT peg deviation: how far from $1.00 (in %) counts as anomalous.
# Real depeg events (e.g. USDC/USDT stress episodes) are typically well
# over 1%; ordinary stablecoin noise is usually under 0.1-0.2%. 0.5% is
# a conservative middle ground for a demo pipeline.
PEG_TARGET_USD = 1.00
PEG_DEVIATION_THRESHOLD_PCT = 0.5#0.03
NARRATIVE_MODEL = "openai/gpt-oss-120b"
