from __future__ import annotations

import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, field_validator

app = FastAPI(
    title="Project 3 Hosted Anomaly Monitor API",
    version="0.1.0",
    description="Safe lifecycle API for the hosted crypto anomaly pipeline.",
)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("DASHBOARD_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH"],
    allow_headers=["Content-Type", "Authorization"],
)

SECRET_PATTERN = re.compile(
    r"(?i)(?:api[_-]?key|authorization|password|secret|token)\s*[=:]\s*[^\s,;]+|bearer\s+[^\s,;]+"
)
MAX_ERROR_LENGTH = 500


def alert_idempotency_key(item: "AlertCreate") -> str:
    return f"{item.anomaly_id}:{item.alert_type}:{item.channel}"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def safe_error_summary(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = SECRET_PATTERN.sub("[REDACTED]", str(value))
    cleaned = re.sub(r"https?://\S+", "[URL_REDACTED]", cleaned)
    return cleaned[:MAX_ERROR_LENGTH]


def database_url() -> str | None:
    return os.getenv("SUPABASE_DATABASE_URL") or os.getenv("DATABASE_URL")


class PipelineRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    run_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    started_at: datetime = Field(default_factory=utc_now)
    status: str = Field(default="running", pattern="^(running|succeeded|failed|partial)$")
    readings_fetched: int = Field(default=0, ge=0)
    readings_inserted: int = Field(default=0, ge=0)
    quality_flags_count: int = Field(default=0, ge=0)
    anomalies_count: int = Field(default=0, ge=0)
    narratives_count: int = Field(default=0, ge=0)
    alerts_created: int = Field(default=0, ge=0)
    alerts_sent: int = Field(default=0, ge=0)
    alerts_failed: int = Field(default=0, ge=0)
    stage_timings_ms: dict[str, float] = Field(default_factory=dict)
    error_summary: str | None = None

    @field_validator("error_summary")
    @classmethod
    def sanitize_error(cls, value: str | None) -> str | None:
        return safe_error_summary(value)


class PipelineRunUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(pattern="^(running|succeeded|failed|partial)$")
    completed_at: datetime | None = None
    readings_fetched: int | None = Field(default=None, ge=0)
    readings_inserted: int | None = Field(default=None, ge=0)
    quality_flags_count: int | None = Field(default=None, ge=0)
    anomalies_count: int | None = Field(default=None, ge=0)
    narratives_count: int | None = Field(default=None, ge=0)
    alerts_created: int | None = Field(default=None, ge=0)
    alerts_sent: int | None = Field(default=None, ge=0)
    alerts_failed: int | None = Field(default=None, ge=0)
    stage_timings_ms: dict[str, float] | None = None
    error_summary: str | None = None

    @field_validator("error_summary")
    @classmethod
    def sanitize_error(cls, value: str | None) -> str | None:
        return safe_error_summary(value)


class PipelineRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    run_id: uuid.UUID
    started_at: datetime
    completed_at: datetime | None
    status: str
    readings_fetched: int
    readings_inserted: int
    quality_flags_count: int
    anomalies_count: int
    narratives_count: int
    alerts_created: int
    alerts_sent: int
    alerts_failed: int
    stage_timings_ms: dict[str, float]
    error_summary: str | None


class AlertCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anomaly_id: int = Field(gt=0)
    narrative_id: int | None = Field(default=None, gt=0)
    run_id: uuid.UUID | None = None
    alert_type: str = Field(min_length=1, max_length=80)
    severity: str = Field(pattern="^(low|medium|high)$")
    channel: str = Field(default="webhook", min_length=1, max_length=40)


class AlertRecord(BaseModel):
    alert_id: uuid.UUID
    anomaly_id: int
    narrative_id: int | None
    run_id: uuid.UUID | None
    alert_type: str
    severity: str
    channel: str
    idempotency_key: str
    status: str
    attempt_count: int
    last_error: str | None
    created_at: datetime
    sent_at: datetime | None


class AlertDecision(BaseModel):
    alert: AlertRecord
    created: bool
    delivery_enabled: bool = False
    message: str = "Alert persisted; delivery remains disabled until Module 5B."


def dry_run_delivery(alert: AlertRecord) -> dict[str, Any]:
    """Render the delivery boundary without performing network I/O."""
    return {
        "alert_id": str(alert.alert_id),
        "status": "dry_run",
        "delivered": False,
        "reason": "Automatic alert delivery is disabled until Module 5B.",
    }


class RunRepository:
    def __init__(self, pool: asyncpg.Pool | None):
        self.pool = pool

    async def create(self, item: PipelineRunCreate) -> PipelineRun:
        if not self.pool:
            raise HTTPException(status_code=503, detail="Database is not configured")
        query = """
            INSERT INTO pipeline_runs (
                run_id, started_at, status, readings_fetched, readings_inserted,
                quality_flags_count, anomalies_count, narratives_count,
                alerts_created, alerts_sent, alerts_failed, stage_timings_ms,
                error_summary
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12::jsonb,$13)
            RETURNING *
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                item.run_id,
                item.started_at,
                item.status,
                item.readings_fetched,
                item.readings_inserted,
                item.quality_flags_count,
                item.anomalies_count,
                item.narratives_count,
                item.alerts_created,
                item.alerts_sent,
                item.alerts_failed,
                __import__("json").dumps(item.stage_timings_ms),
                item.error_summary,
            )
        return PipelineRun(**dict(row))

    async def update(self, run_id: uuid.UUID, item: PipelineRunUpdate) -> PipelineRun:
        if not self.pool:
            raise HTTPException(status_code=503, detail="Database is not configured")
        values: dict[str, Any] = item.model_dump(exclude_unset=True)
        if values.get("completed_at") is None and values.get("status") in {"succeeded", "failed", "partial"}:
            values["completed_at"] = utc_now()
        if "stage_timings_ms" in values:
            import json
            values["stage_timings_ms"] = json.dumps(values["stage_timings_ms"])
        assignments = []
        params: list[Any] = [run_id]
        for index, (key, value) in enumerate(values.items(), start=2):
            assignments.append(f"{key} = ${index}" + ("::jsonb" if key == "stage_timings_ms" else ""))
            params.append(value)
        if not assignments:
            raise HTTPException(status_code=400, detail="No update fields supplied")
        query = f"UPDATE pipeline_runs SET {', '.join(assignments)} WHERE run_id = $1 RETURNING *"
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, *params)
        if not row:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        return PipelineRun(**dict(row))

    async def list(self, limit: int) -> list[PipelineRun]:
        if not self.pool:
            raise HTTPException(status_code=503, detail="Database is not configured")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM pipeline_runs ORDER BY started_at DESC LIMIT $1", limit
            )
        return [PipelineRun(**dict(row)) for row in rows]


class AlertRepository:
    def __init__(self, pool: asyncpg.Pool | None):
        self.pool = pool

    async def create_idempotent(self, item: AlertCreate) -> tuple[AlertRecord, bool]:
        if not self.pool:
            raise HTTPException(status_code=503, detail="Database is not configured")
        idempotency_key = alert_idempotency_key(item)
        query = """
            INSERT INTO alerts (
                anomaly_id, narrative_id, run_id, alert_type, severity,
                channel, idempotency_key, status
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,'pending')
            ON CONFLICT (idempotency_key) DO NOTHING
            RETURNING *
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                query,
                item.anomaly_id,
                item.narrative_id,
                item.run_id,
                item.alert_type,
                item.severity,
                item.channel,
                idempotency_key,
            )
            created = row is not None
            if row is None:
                row = await conn.fetchrow(
                    "SELECT * FROM alerts WHERE idempotency_key = $1",
                    idempotency_key,
                )
        if row is None:
            raise HTTPException(status_code=500, detail="Alert persistence failed")
        return AlertRecord(**dict(row)), created

    async def list(self, limit: int) -> list[AlertRecord]:
        if not self.pool:
            raise HTTPException(status_code=503, detail="Database is not configured")
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM alerts ORDER BY created_at DESC LIMIT $1", limit
            )
        return [AlertRecord(**dict(row)) for row in rows]


@app.on_event("startup")
async def open_database() -> None:
    url = database_url()
    app.state.pool = await asyncpg.create_pool(url, min_size=1, max_size=5) if url else None
    app.state.repo = RunRepository(app.state.pool)
    app.state.alert_repo = AlertRepository(app.state.pool)


@app.on_event("shutdown")
async def close_database() -> None:
    pool = getattr(app.state, "pool", None)
    if pool:
        await pool.close()


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "service": "project3-hosted-monitor-api",
        "status": "ok",
        "database_configured": bool(database_url()),
        "alert_delivery_enabled": False,
        "alert_delivery_status": "not_live_module_5b_pending",
    }


@app.post("/api/pipeline-runs", response_model=PipelineRun, status_code=201)
async def start_pipeline_run(payload: PipelineRunCreate) -> PipelineRun:
    return await app.state.repo.create(payload)


@app.patch("/api/pipeline-runs/{run_id}", response_model=PipelineRun)
async def finish_pipeline_run(run_id: uuid.UUID, payload: PipelineRunUpdate) -> PipelineRun:
    return await app.state.repo.update(run_id, payload)


@app.get("/api/pipeline-runs", response_model=list[PipelineRun])
async def recent_pipeline_runs(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[PipelineRun]:
    return await app.state.repo.list(limit)


@app.post("/api/alerts", response_model=AlertDecision, status_code=201)
async def create_alert(payload: AlertCreate) -> AlertDecision:
    alert, created = await app.state.alert_repo.create_idempotent(payload)
    return AlertDecision(alert=alert, created=created)


@app.get("/api/alerts", response_model=list[AlertRecord])
async def recent_alerts(
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AlertRecord]:
    return await app.state.alert_repo.list(limit)


@app.get("/api/readiness")
async def readiness() -> dict[str, Any]:
    return {
        "pipeline_run_lifecycle": "ready",
        "supabase_persistence": "configured" if database_url() else "awaiting_server_configuration",
        "groq_narratives": bool(os.getenv("GROQ_API_KEY")),
        "openrouter_fallback": bool(os.getenv("OPENROUTER_API_KEY")),
        "automatic_alert_delivery": "disabled_until_module_5b",
    }
