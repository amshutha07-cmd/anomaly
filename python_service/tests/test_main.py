import unittest
import asyncio
import uuid
from datetime import datetime, timezone


from python_service.app.main import (
    AlertCreate,
    AlertDecision,
    AlertRecord,
    AlertRepository,
    app,
    create_alert,
    dry_run_delivery,
    PipelineRunCreate,
    PipelineRunUpdate,
    alert_idempotency_key,
    safe_error_summary,
)


class FakeConnection:
    def __init__(self):
        self.rows = {}

    async def fetchrow(self, query, *args):
        if query.strip().startswith("INSERT INTO alerts"):
            key = args[6]
            if key in self.rows:
                return None
            row = {
                "alert_id": uuid.uuid4(),
                "anomaly_id": args[0],
                "narrative_id": args[1],
                "run_id": args[2],
                "alert_type": args[3],
                "severity": args[4],
                "channel": args[5],
                "idempotency_key": key,
                "status": "pending",
                "attempt_count": 0,
                "last_error": None,
                "created_at": datetime.now(timezone.utc),
                "sent_at": None,
            }
            self.rows[key] = row
            return row
        return self.rows.get(args[0])

    async def fetch(self, query, limit):
        return list(self.rows.values())[:limit]


class FakeAcquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakePool:
    def __init__(self):
        self.connection = FakeConnection()

    def acquire(self):
        return FakeAcquire(self.connection)


class Module5A1ContractTests(unittest.TestCase):
    def test_error_summary_redacts_secrets_and_urls(self):
        value = "Bearer abc123 api_key=secret-value failed at https://internal.example/run"
        cleaned = safe_error_summary(value)
        self.assertNotIn("abc123", cleaned)
        self.assertNotIn("secret-value", cleaned)
        self.assertNotIn("https://internal.example/run", cleaned)
        self.assertIn("[REDACTED]", cleaned)
        self.assertIn("[URL_REDACTED]", cleaned)

    def test_run_defaults_to_running_with_utc_start(self):
        run = PipelineRunCreate()
        self.assertEqual(run.status, "running")
        self.assertIsNotNone(run.run_id)
        self.assertEqual(run.started_at.tzinfo, timezone.utc)

    def test_run_rejects_unknown_status(self):
        with self.assertRaises(ValueError):
            PipelineRunUpdate(status="queued")

    def test_alert_key_is_deterministic_per_anomaly_type_and_channel(self):
        alert = AlertCreate(anomaly_id=21, alert_type="market_anomaly", severity="high")
        self.assertEqual(alert_idempotency_key(alert), "21:market_anomaly:webhook")
        self.assertEqual(alert_idempotency_key(alert), alert_idempotency_key(alert))

    def test_alert_rejects_invalid_severity(self):
        with self.assertRaises(ValueError):
            AlertCreate(anomaly_id=21, alert_type="market_anomaly", severity="urgent")

    def test_alert_decision_keeps_delivery_disabled(self):
        alert = AlertDecision.model_construct(
            alert_id=None,
            alert=None,
            created=False,
        )
        self.assertFalse(alert.delivery_enabled)
        self.assertEqual(alert.message, "Alert persisted; delivery remains disabled until Module 5B.")

    def test_alert_endpoint_suppresses_duplicate_requests(self):
        async def exercise():
            app.state.alert_repo = AlertRepository(FakePool())
            payload = AlertCreate(anomaly_id=21, alert_type="market_anomaly", severity="high")
            first = await create_alert(payload)
            second = await create_alert(payload)
            return first, second

        first, second = asyncio.run(exercise())
        self.assertTrue(first.created)
        self.assertFalse(second.created)
        self.assertEqual(first.alert.alert_id, second.alert.alert_id)
        self.assertFalse(first.delivery_enabled)
        self.assertFalse(second.delivery_enabled)

    def test_dry_run_does_not_deliver(self):
        alert = AlertRecord(
            alert_id=uuid.uuid4(), anomaly_id=21, narrative_id=21, run_id=None,
            alert_type="market_anomaly", severity="high", channel="webhook",
            idempotency_key="21:market_anomaly:webhook", status="pending",
            attempt_count=0, last_error=None, created_at=datetime.now(timezone.utc), sent_at=None,
        )
        result = dry_run_delivery(alert)
        self.assertEqual(result["status"], "dry_run")
        self.assertFalse(result["delivered"])

    def test_repository_suppresses_duplicate_alerts(self):
        async def exercise():
            repository = AlertRepository(FakePool())
            payload = AlertCreate(anomaly_id=21, alert_type="market_anomaly", severity="high")
            first, first_created = await repository.create_idempotent(payload)
            second, second_created = await repository.create_idempotent(payload)
            return first, first_created, second, second_created

        first, first_created, second, second_created = asyncio.run(exercise())
        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.alert_id, second.alert_id)
        self.assertEqual(second.status, "pending")

    def test_finished_update_accepts_stage_timings(self):
        update = PipelineRunUpdate(
            status="succeeded",
            completed_at=datetime.now(timezone.utc),
            stage_timings_ms={"ingestion": 42.5, "quality": 3.1},
        )
        self.assertEqual(update.status, "succeeded")
        self.assertEqual(update.stage_timings_ms["ingestion"], 42.5)


if __name__ == "__main__":
    unittest.main()
