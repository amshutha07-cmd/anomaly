# Project 3: Live Anomaly Detection Agent 🚀

A real-time anomaly detection agent that ingests live data streams from a free public API on a schedule, applies statistical anomaly detection algorithms, uses an LLM to generate plain-language root-cause incident narratives, and triggers automated alerts.

---

## 🏗️ Architecture & Modules
- **Module 1: Live Data Ingestion** (`src/ingest.py`) — Real-time API polling, deduplication, latency metrics, and SQLite storage.
- **Module 2: Data Quality & Schema Integrity** (`src/quality_checks.py`) — Boundary validation, null handling, timestamp monotonicity.
- **Module 3: Anomaly Detection Engine** (`src/anomaly_detect.py`) — Multi-method detection (Rolling Z-Score, IQR, velocity spikes).
- **Module 4: Incident Narrative Generation** (`src/narrative_llm.py`) — LLM-driven root-cause explanations and severity assessment.
- **Module 5: Alerting & Dispatch** (`src/alert.py`) — Multi-channel notifications (Console, Log, Webhooks).
- **Module 6: Pipeline Orchestration** (`pipeline_runner.py`) — Scheduled cron execution with error boundaries.

---

## ⚡ Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Module 1 Ingestion Once (Smoke Test)
```bash
python -m src.ingest
```

### 3. Run Scheduled Pipeline Runner
```bash
# Run continuous live monitoring loop every 60 seconds
python pipeline_runner.py --interval 60

# Or execute a single full iteration
python pipeline_runner.py --single-run
```

---

## 📊 Database Telemetry & Logs
All data and telemetry are stored in SQLite at `logs/run_history.db`:
- `raw_ingest`: Parsed time-series records.
- `ingest_metrics`: Telemetry on fetch latency, DB latency, HTTP codes.
- `pipeline_runs`: High-level run orchestration audit log.
