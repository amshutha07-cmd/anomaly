# """
# Live ingestion: pulls BTC/ETH/USDT prices from CoinGecko (primary),
# falling back to Binance's public ticker per-asset if CoinGecko fails
# or times out after retries.

# Why failover matters here (not just retries): a custody/infra context
# cares about what happens when your *only* price source goes down or
# returns bad data. Retrying the same flaky source three times and then
# giving up is weaker than having an independent second source to lean
# on. This module tries CoinGecko with backoff first; only if that
# exhausts its retries does it fall over to Binance for that asset, and
# it records is_failover=1 so you can see how often that happened.
# """

# import logging
# import time

# import requests

# import config

# logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
# log = logging.getLogger("ingest")


# def _fetch_with_retry(fetch_fn, *args, max_retries=None, backoff_base=None, **kwargs):
#     """
#     Generic retry wrapper with exponential backoff.
#     Returns (result, latency_ms) on success, raises the last exception
#     if all attempts are exhausted.
#     """
#     max_retries = max_retries or config.MAX_RETRIES
#     backoff_base = backoff_base or config.BACKOFF_BASE

#     last_exc = None
#     for attempt in range(max_retries):
#         start = time.perf_counter()
#         try:
#             result = fetch_fn(*args, **kwargs)
#             latency_ms = (time.perf_counter() - start) * 1000
#             return result, latency_ms
#         except (requests.RequestException, ValueError) as exc:
#             last_exc = exc
#             wait = backoff_base ** attempt
#             log.warning(
#                 "fetch attempt %d/%d failed (%s) — retrying in %.2fs",
#                 attempt + 1, max_retries, exc, wait,
#             )
#             if attempt < max_retries - 1:
#                 time.sleep(wait)
#     raise last_exc


# def _fetch_coingecko_all() -> dict:
#     """
#     Single batched call for all assets — CoinGecko's /simple/price
#     endpoint supports comma-separated ids, so one request covers the
#     whole asset universe rather than one call per asset.
#     """
#     ids = ",".join(config.ASSETS.keys())
#     resp = requests.get(
#         config.COINGECKO_URL,
#         params={
#             "ids": ids,
#             "vs_currencies": "usd",
#             "include_market_cap": "true",
#             "include_24hr_vol": "true",
#         },
#         timeout=config.REQUEST_TIMEOUT_SECONDS,
#     )
#     resp.raise_for_status()
#     data = resp.json()
#     if not data:
#         raise ValueError("CoinGecko returned empty payload")
#     return data


# def _fetch_binance_one(binance_symbol: str) -> dict:
#     """Per-asset Binance failover call (Binance has no batched-by-id endpoint we rely on here)."""
#     resp = requests.get(
#         config.BINANCE_TICKER_URL,
#         params={"symbol": binance_symbol},
#         timeout=config.REQUEST_TIMEOUT_SECONDS,
#     )
#     resp.raise_for_status()
#     data = resp.json()
#     if "lastPrice" not in data:
#         raise ValueError(f"Unexpected Binance payload for {binance_symbol}: {data}")
#     return data


# def fetch_all(recorded_at: str) -> list[dict]:
#     """
#     Fetch current price/volume/market cap for every configured asset,
#     from CoinGecko first, falling back to Binance per-asset on failure.
#     Returns a list of reading dicts ready for db.insert_readings_batch.
#     """
#     readings = []

#     # --- Primary: CoinGecko, batched ---
#     coingecko_data = None
#     coingecko_latency_ms = None
#     try:
#         coingecko_data, coingecko_latency_ms = _fetch_with_retry(_fetch_coingecko_all)
#         log.info("CoinGecko fetch OK (%.1f ms)", coingecko_latency_ms)
#     except Exception as exc:
#         log.error("CoinGecko exhausted retries: %s — will attempt Binance failover for all assets", exc)

#     for asset_id, meta in config.ASSETS.items():
#         if coingecko_data and asset_id in coingecko_data:
#             d = coingecko_data[asset_id]
#             readings.append({
#                 "recorded_at": recorded_at,
#                 "asset_id": asset_id,
#                 "source": "coingecko",
#                 "price_usd": d.get("usd"),
#                 "volume_24h_usd": d.get("usd_24h_vol"),
#                 "market_cap_usd": d.get("usd_market_cap"),
#                 "is_failover": 0,
#                 "fetch_latency_ms": coingecko_latency_ms,
#             })
#             continue

#         # --- Failover: Binance, per-asset ---
#         if meta.get("is_stablecoin"):
#             # USDTUSDT isn't a meaningful Binance pair (an asset quoted
#             # against itself). Documented rather than silently skipped:
#             # a real production system would use USDT/BUSD or a fiat
#             # on-ramp pair here. Skipping cleanly, with a log line, is
#             # more honest than faking a data point.
#             log.warning("No Binance failover available for stablecoin %s vs itself — skipping", asset_id)
#             continue

#         try:
#             b_data, b_latency_ms = _fetch_with_retry(_fetch_binance_one, meta["binance_symbol"])
#             readings.append({
#                 "recorded_at": recorded_at,
#                 "asset_id": asset_id,
#                 "source": "binance",
#                 "price_usd": float(b_data["lastPrice"]),
#                 "volume_24h_usd": float(b_data.get("quoteVolume", 0)) or None,
#                 "market_cap_usd": None,  # Binance ticker doesn't report market cap
#                 "is_failover": 1,
#                 "fetch_latency_ms": b_latency_ms,
#             })
#             log.info("Binance failover OK for %s (%.1f ms)", asset_id, b_latency_ms)
#         except Exception as exc:
#             log.error("Both CoinGecko and Binance failed for %s: %s — no reading this poll", asset_id, exc)

#     return readings
"""
Live ingestion: pulls BTC/ETH/USDT prices from CoinGecko AND Binance
every poll (not failover-only) — a non-stablecoin asset is dual-sourced
on every successful poll, not just when the primary fails.

Why dual-source-always, not failover-only: reconciling two independent
sources (Module 2) can only catch a bad price if both sources actually
reported that poll. A failover-only design only calls the secondary
source when the primary is already down — meaning reconciliation would
never run under normal conditions, exactly when you most want to be
checking. Always fetching both means every poll gets a genuine
cross-source check, and `is_failover` still means what it says: it's
only 1 when CoinGecko failed and Binance's reading is the *only* one
available for that asset that poll — not "Binance was called."
"""

import logging
import time

import requests

import config

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ingest")


def _fetch_with_retry(fetch_fn, *args, max_retries=None, backoff_base=None, **kwargs):
    """
    Generic retry wrapper with exponential backoff.
    Returns (result, latency_ms) on success, raises the last exception
    if all attempts are exhausted.
    """
    max_retries = max_retries or config.MAX_RETRIES
    backoff_base = backoff_base or config.BACKOFF_BASE

    last_exc = None
    for attempt in range(max_retries):
        start = time.perf_counter()
        try:
            result = fetch_fn(*args, **kwargs)
            latency_ms = (time.perf_counter() - start) * 1000
            return result, latency_ms
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            wait = backoff_base ** attempt
            log.warning(
                "fetch attempt %d/%d failed (%s) — retrying in %.2fs",
                attempt + 1, max_retries, exc, wait,
            )
            if attempt < max_retries - 1:
                time.sleep(wait)
    raise last_exc


def _fetch_coingecko_all() -> dict:
    """
    Single batched call for all assets — CoinGecko's /simple/price
    endpoint supports comma-separated ids, so one request covers the
    whole asset universe rather than one call per asset.
    """
    ids = ",".join(config.ASSETS.keys())
    resp = requests.get(
        config.COINGECKO_URL,
        params={
            "ids": ids,
            "vs_currencies": "usd",
            "include_market_cap": "true",
            "include_24hr_vol": "true",
        },
        timeout=config.REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        raise ValueError("CoinGecko returned empty payload")
    return data


def _fetch_binance_one(binance_symbol: str) -> dict:
    """Per-asset Binance call (Binance has no batched-by-id endpoint we rely on here)."""
    resp = requests.get(
        config.BINANCE_TICKER_URL,
        params={"symbol": binance_symbol},
        timeout=config.REQUEST_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    if "lastPrice" not in data:
        raise ValueError(f"Unexpected Binance payload for {binance_symbol}: {data}")
    return data


def fetch_all(recorded_at: str) -> list[dict]:
    """
    Fetch current price/volume/market cap for every configured asset,
    from BOTH CoinGecko and Binance every poll (dual-source, not
    failover-only). Returns a list of reading dicts ready for
    db.insert_readings_batch — up to 2 rows per non-stablecoin asset.
    """
    readings = []

    # --- CoinGecko: batched, all assets in one call ---
    coingecko_data = None
    coingecko_latency_ms = None
    try:
        coingecko_data, coingecko_latency_ms = _fetch_with_retry(_fetch_coingecko_all)
        log.info("CoinGecko fetch OK (%.1f ms)", coingecko_latency_ms)
    except Exception as exc:
        log.error("CoinGecko exhausted retries: %s — Binance will be this poll's only source", exc)

    for asset_id, meta in config.ASSETS.items():
        got_coingecko = False

        if coingecko_data and asset_id in coingecko_data:
            d = coingecko_data[asset_id]
            readings.append({
                "recorded_at": recorded_at,
                "asset_id": asset_id,
                "source": "coingecko",
                "price_usd": d.get("usd"),
                "volume_24h_usd": d.get("usd_24h_vol"),
                "market_cap_usd": d.get("usd_market_cap"),
                "is_failover": 0,
                "fetch_latency_ms": coingecko_latency_ms,
            })
            got_coingecko = True

        # --- Binance: called every poll for non-stablecoins, not just
        # on CoinGecko failure. is_failover is set based on whether
        # CoinGecko actually covered this asset this poll. ---
        if meta.get("is_stablecoin"):
            if not got_coingecko:
                log.warning("No Binance equivalent for stablecoin %s vs itself, and CoinGecko missed it — no reading this poll", asset_id)
            continue

        try:
            b_data, b_latency_ms = _fetch_with_retry(_fetch_binance_one, meta["binance_symbol"])
            readings.append({
                "recorded_at": recorded_at,
                "asset_id": asset_id,
                "source": "binance",
                "price_usd": float(b_data["lastPrice"]),
                "volume_24h_usd": float(b_data.get("quoteVolume", 0)) or None,
                "market_cap_usd": None,  # Binance ticker doesn't report market cap
                "is_failover": 0 if got_coingecko else 1,
                "fetch_latency_ms": b_latency_ms,
            })
            log.info(
                "Binance fetch OK for %s (%.1f ms)%s",
                asset_id, b_latency_ms, "" if got_coingecko else " [failover — sole source this poll]",
            )
        except Exception as exc:
            if got_coingecko:
                log.warning("Binance secondary fetch failed for %s: %s — CoinGecko reading still recorded, no reconciliation possible this poll", asset_id, exc)
            else:
                log.error("Both CoinGecko and Binance failed for %s: %s — no reading this poll", asset_id, exc)

    return readings