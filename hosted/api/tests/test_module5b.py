import os
import unittest
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from app.main import app, AlertRecord, dry_run_delivery
from app.module5b import build_webhook_payload, delivery_enabled, retry_delay_seconds


class Module5BContractTests(unittest.TestCase):
    def test_delivery_is_disabled_by_default(self):
        with patch.dict(os.environ, {"ALERT_DELIVERY_ENABLED": "false"}, clear=False):
            self.assertFalse(delivery_enabled())

    def test_retry_backoff_is_exponential_and_capped(self):
        with patch.dict(os.environ, {"ALERT_RETRY_BACKOFF_SECONDS": "30"}, clear=False):
            self.assertEqual(retry_delay_seconds(1), 30)
            self.assertEqual(retry_delay_seconds(2), 60)
            self.assertEqual(retry_delay_seconds(3), 120)
            self.assertLessEqual(retry_delay_seconds(20), 3600)

    def test_webhook_payload_contains_no_delivery_secret(self):
        row = {
            "alert_id": uuid.uuid4(),
            "anomaly_id": 21,
            "narrative_id": 21,
            "run_id": None,
            "alert_type": "market_anomaly",
            "severity": "high",
            "channel": "webhook",
            "idempotency_key": "21:market_anomaly:webhook",
            "created_at": datetime.now(timezone.utc),
        }
        payload = build_webhook_payload(row)
        self.assertEqual(payload["event"], "crypto_anomaly_alert")
        self.assertNotIn("ALERT_WEBHOOK_URL", payload)
        self.assertNotIn("ALERT_WORKER_TOKEN", payload)

    def test_dry_run_never_delivers(self):
        alert = AlertRecord(
            alert_id=uuid.uuid4(), anomaly_id=21, narrative_id=21, run_id=None,
            alert_type="market_anomaly", severity="high", channel="webhook",
            idempotency_key="21:market_anomaly:webhook", status="pending",
            attempt_count=0, last_error=None, created_at=datetime.now(timezone.utc), sent_at=None,
        )
        result = dry_run_delivery(alert)
        self.assertFalse(result["delivered"])
        self.assertEqual(result["status"], "dry_run")

    def test_module5b_routes_exist(self):
        paths = {(route.path, tuple(sorted(route.methods or []))) for route in app.routes}
        self.assertIn(("/api/alerts/{alert_id}/deliver", ("POST",)), paths)
        self.assertIn(("/api/alerts/{alert_id}/acknowledge", ("PATCH",)), paths)
        self.assertIn(("/api/internal/alerts/dispatch", ("POST",)), paths)


if __name__ == "__main__":
    unittest.main()