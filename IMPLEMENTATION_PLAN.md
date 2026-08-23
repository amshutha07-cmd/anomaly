# Project 3: Live Anomaly Detection Agent — Implementation Plan

## System Overview
An automated real-time monitoring and anomaly detection agent that ingests live metric/weather time-series data from a free public API (Open-Meteo) on a schedule, performs data quality validation, detects statistical & trend anomalies, generates natural-language root-cause narratives via LLM, and triggers actionable alerts.

```
[ Free API: Open-Meteo ]
          │
          ▼
┌───────────────────────┐
│ Module 1: Ingestion   │ ──► [ SQLite: raw_ingest ]
└───────────────────────┘
          │
          ▼
┌───────────────────────┐
│ Module 2: Quality     │ ──► [ SQLite: quality_log ]
└───────────────────────┘
          │
          ▼
┌───────────────────────┐
│ Module 3: Anomaly Det │ ──► [ SQLite: anomaly_log ]
└───────────────────────┘
          │
          ▼
┌───────────────────────┐
│ Module 4: Narrative   │ ──► [ SQLite: narrative_log ]
└───────────────────────┘
          │
          ▼
┌───────────────────────┐
│ Module 5: Alerting    │ ──► [ Console / Log / Webhook ]
└───────────────────────┘
```

---

## Directory Structure
```
live_anonalu/
├── README.md
├── IMPLEMENTATION_PLAN.md
├── requirements.txt
├── config.py
├── src/
│   ├── __init__.py
│   ├── db.py                 # SQLite connection & schema management
│   ├── ingest.py             # Module 1: Live data ingestion
│   ├── quality_checks.py     # Module 2: Data quality assurance & schema validation
│   ├── anomaly_detect.py     # Module 3: Statistical & ML anomaly detection (Z-score, IQR, Rolling)
│   ├── narrative_llm.py      # Module 4: LLM-powered incident narrative generation
│   └── alert.py              # Module 5: Multi-channel alerting engine
├── pipeline_runner.py        # Module 6: End-to-end scheduled pipeline orchestrator
├── logs/
│   └── run_history.db        # Persistent SQLite storage
├── module_notes/
│   ├── module1_notes.md      # Live Data Ingestion deep dive
│   ├── module2_notes.md
│   ├── module3_notes.md
│   ├── module4_notes.md
│   ├── module5_notes.md
│   └── module6_notes.md
└── resume_numbers.md         # Quantified impact metrics for resume bullet points
```

---

## Module Breakdown

### Module 1: Live Data Ingestion (`src/ingest.py`)
- **Source**: Open-Meteo Forecast & Current API (Free tier, no API key required, reliable latency).
- **Metrics Tracked**:
  - `temperature_2m` (°C)
  - `relative_humidity_2m` (%)
  - `apparent_temperature` (°C)
  - `precipitation` (mm)
  - `wind_speed_10m` (km/h)
  - `surface_pressure` (hPa)
- **Features**:
  - Resilient HTTP requests with exponential backoff & timeout handling.
  - Granular latency profiling (network ms, parsing ms, write ms).
  - Deduplication via source timestamp hashing / unique indexing.
  - Writes to SQLite `raw_ingest` table with ingestion metadata.

### Module 2: Data Quality & Integrity Checks (`src/quality_checks.py`)
- Null / None checks, boundary validation (e.g. humidity 0-100%, valid pressure).
- Timestamp monotonically increasing & gap detection.
- Log pass/fail counts to `quality_log`.

### Module 3: Anomaly Detection Engine (`src/anomaly_detect.py`)
- Rolling Z-Score (standard deviation deviations > threshold).
- Interquartile Range (IQR) fence check for non-normal distributions.
- Velocity / Spike detector (first-order derivative jumps).

### Module 4: Incident Narrative Generation (`src/narrative_llm.py`)
- Formulates prompt with historical baseline, anomaly value, delta %, and context.
- Generates human-readable RCA (Root Cause Analysis) summary.

### Module 5: Alerting Engine (`src/alert.py`)
- Threshold-based severity routing (INFO, WARNING, CRITICAL).
- Structured output to console, `alerts.log`, and webhook dispatch.

### Module 6: Pipeline Orchestration (`pipeline_runner.py`)
- Scheduled execution loop using `schedule` / interval timer.
- Run-level metadata tracking (total latency, error handling, status logging).
