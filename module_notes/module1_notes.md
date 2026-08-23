# Module 1 Deep Dive: Live Data Ingestion

## 1. Objective & Architecture
Module 1 is the streaming ingestion foundation for the real-time anomaly detection pipeline. It is responsible for continuously polling the external API, parsing high-dimensional numerical observation vectors, persisting historical observations for sliding-window analysis, and capturing granular latency and reliability telemetry.

```
┌─────────────────────────────────┐
│     Open-Meteo REST API         │
│ (https://api.open-meteo.com)    │
└────────────────┬────────────────┘
                 │ HTTP GET (with Exponential Backoff Retry)
                 ▼
┌─────────────────────────────────┐
│  src/ingest.py (fetch_live_data)│
│  - Response parsing             │
│  - Precision profiling (perf_c) │
└────────────────┬────────────────┘
                 │
                 ├──► INSERT OR IGNORE ──► SQLite `raw_ingest` table
                 │                         (deduped on timestamp + coordinates)
                 │
                 └──► INSERT ───────────► SQLite `ingest_metrics` table
                                           (HTTP code, latency, success/failure)
```

---

## 2. API Selection & Contract
- **Provider**: Open-Meteo Weather Forecast & Real-Time API (Non-commercial open-access tier, no API keys or billing overhead).
- **Target Coordinates**: `28.6139° N, 77.2090° E` (New Delhi, India).
- **Metrics Collected**:
  1. `temperature_2m` (°C): Ambient air temperature at 2 meters above ground.
  2. `relative_humidity_2m` (%): Relative humidity percentage [0-100%].
  3. `apparent_temperature` (°C): Perceived heat index / wind chill.
  4. `precipitation` (mm): Precipitation liquid water equivalent.
  5. `wind_speed_10m` (km/h): Wind velocity at 10 meters.
  6. `surface_pressure` (hPa): Atmospheric air pressure at ground elevation.

---

## 3. Reliability & Failure Handling
1. **Exponential Backoff Strategy**:
   - `MAX_RETRIES = 3`
   - `BACKOFF_FACTOR = 1.5`
   - Wait times between retries: $1.5^1 = 1.5s$, $1.5^2 = 2.25s$.
2. **Deduplication Engine**:
   - SQLite composite unique constraint on `(recorded_at, latitude, longitude)`.
   - Idempotent writes via `INSERT OR IGNORE` ensure zero duplicate ingestion spikes during network restarts or overlapping schedules.
3. **Operational Telemetry**:
   - Every fetch logs execution duration in milliseconds (`fetch_latency_ms`, `db_write_latency_ms`, `total_latency_ms`).
   - Tracks HTTP status codes, records inserted vs. records skipped.

---

## 4. Key Schema Specifications

### `raw_ingest` Table
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment primary key |
| `recorded_at` | TEXT | Observation timestamp from source (ISO8601) |
| `ingested_at` | TEXT | Timestamp when ingestion worker processed row (ISO8601) |
| `latitude` | REAL | Geographic coordinate latitude |
| `longitude` | REAL | Geographic coordinate longitude |
| `elevation` | REAL | Elevation in meters |
| `temperature_2m` | REAL | Air temperature (°C) |
| `relative_humidity_2m` | REAL | Humidity percentage |
| `apparent_temperature` | REAL | Feels-like temperature (°C) |
| `precipitation` | REAL | Precipitation amount (mm) |
| `wind_speed_10m` | REAL | Wind speed (km/h) |
| `surface_pressure` | REAL | Surface atmospheric pressure (hPa) |
| `raw_payload` | TEXT | Raw JSON string response for auditability & replay |

### `ingest_metrics` Table
| Column | Type | Description |
|---|---|---|
| `run_id` | INTEGER PK | Primary key |
| `executed_at` | TEXT | Ingestion timestamp |
| `http_status` | INTEGER | HTTP Status Code (200, 429, 500, etc.) |
| `fetch_latency_ms` | REAL | API network round-trip time in milliseconds |
| `db_write_latency_ms` | REAL | SQLite disk commit time in milliseconds |
| `total_latency_ms` | REAL | Sum of network + processing + write latency |
| `records_inserted` | INTEGER | Count of new records written |
| `records_skipped` | INTEGER | Count of duplicate records skipped |
| `status` | TEXT | `SUCCESS` or `FAILED` |
| `error_message` | TEXT | Exception or HTTP error details |
