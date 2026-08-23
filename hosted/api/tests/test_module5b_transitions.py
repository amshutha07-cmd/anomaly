import asyncio
import os
import unittest
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.module5b import acknowledge_alert, deliver_alert


class _Acquire:
    def __init__(self, connection):
        self.connection = connection

    async def __aenter__(self):
        return self.connection

    async def __aexit__(self, exc_type, exc, tb):
        return False


class _Connection:
    def __init__(self):
        self.alert = {
            "alert_id": uuid.uuid4(),
            "anomaly_id": 21,
            "narrative_id": 21,
            "run_id": None,
            "alert_type": "market_anomaly",
            "severity": "high",
            "channel": "webhook",
            "idempotency_key": "21:market_anomaly:webhook",
            "status": "pending",
            "attempt_count": 0,
            "last_error": None,
            "created_at": datetime.now(timezone.utc),
            "sent_at": None,
            "acknowledged_at": None,
            "next_attempt_at": None,
            "last_attempt_at": None,
        }
        self.attempts = []

    async def fetchrow(self, query, *args):
        normalized = " ".join(query.split())
        if normalized.startswith("SELECT * FROM alerts"):
            return dict(self.alert)

        if "status = 'acknowledged'" in normalized:
            if self.alert["status"] != "sent":
                return None
            self.alert["status"] = "acknowledged"
            self.alert["acknowledged_at"] = args[1]
            return dict(self.alert)

        if normalized.startswith("UPDATE alerts") and "RETURNING *" in normalized:
            now = args[1]
            max_count = args[2]
            due = self.alert["next_attempt_at"] is None or self.alert["next_attempt_at"] <= now
            if self.alert["status"] not in {"pending", "failed"}:
                return None
            if self.alert["attempt_count"] >= max_count or not due:
                return None
            self.alert["status"] = "sending"
            self.alert["attempt_count"] += 1
            self.alert["last_attempt_at"] = now
            self.alert["last_error"] = None
            return dict(self.alert)

        return None

    async def execute(self, query, *args):
        normalized = " ".join(query.split())
        if normalized.startswith("INSERT INTO alert_delivery_attempts"):
            self.attempts.append({
                "attempt_id": args[0],
                "alert_id": args[1],
                "attempt_number": args[2],
                "status": "started",
            })
        elif normalized.startswith("UPDATE alerts"):
            self.alert["status"] = args[1]
            self.alert["sent_at"] = args[2]
            self.alert["next_attempt_at"] = args[3]
            self.alert["last_error"] = args[4]
        elif normalized.startswith("UPDATE alert_delivery_attempts"):
            attempt = next(item for item in self.attempts if item["attempt_id"] == args[0])
            attempt.update({"status": args[1], "response_code": args[2], "error_summary": args[3]})


class _Pool:
    def __init__(self):
        self.connection = _Connection()

    def acquire(self):
        return _Acquire(self.connection)


class Module5BTransitionTests(unittest.TestCase):
    def test_failed_delivery_records_attempt_and_schedules_retry(self):
        async def exercise():
            pool = _Pool()
            with patch.dict(os.environ, {
                "ALERT_DELIVERY_ENABLED": "true",
                "ALERT_WEBHOOK_URL": "https://example.invalid/webhook",
                "ALERT_MAX_ATTEMPTS": "2",
                "ALERT_RETRY_BACKOFF_SECONDS": "1",
            }, clear=False), patch("app.module5b._post_webhook", return_value=(False, 503, "provider unavailable")):
                result = await deliver_alert(pool, pool.connection.alert["alert_id"])
            return pool, result

        pool, result = asyncio.run(exercise())
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["delivered"])
        self.assertTrue(result["retry_scheduled"])
        self.assertEqual(result["alert"]["attempt_count"], 1)
        self.assertIsNotNone(result["alert"]["next_attempt_at"])
        self.assertEqual(len(pool.connection.attempts), 1)
        self.assertEqual(pool.connection.attempts[0]["attempt_number"], 1)
        self.assertEqual(pool.connection.attempts[0]["status"], "failed")

    def test_retry_succeeds_then_acknowledgement_is_idempotent(self):
        async def exercise():
            pool = _Pool()
            env = {
                "ALERT_DELIVERY_ENABLED": "true",
                "ALERT_WEBHOOK_URL": "https://example.invalid/webhook",
                "ALERT_MAX_ATTEMPTS": "3",
                "ALERT_RETRY_BACKOFF_SECONDS": "1",
            }
            with patch.dict(os.environ, env, clear=False), patch(
                "app.module5b._post_webhook",
                side_effect=[(False, 503, "temporary failure"), (True, 202, None)],
            ):
                failed = await deliver_alert(pool, pool.connection.alert["alert_id"])
                pool.connection.alert["next_attempt_at"] = datetime.now(timezone.utc) - timedelta(seconds=1)
                sent = await deliver_alert(pool, pool.connection.alert["alert_id"])
            acknowledged = await acknowledge_alert(pool, pool.connection.alert["alert_id"])
            acknowledged_again = await acknowledge_alert(pool, pool.connection.alert["alert_id"])
            return pool, failed, sent, acknowledged, acknowledged_again

        pool, failed, sent, acknowledged, acknowledged_again = asyncio.run(exercise())
        self.assertEqual(failed["status"], "failed")
        self.assertEqual(sent["status"], "sent")
        self.assertTrue(sent["delivered"])
        self.assertEqual(sent["alert"]["attempt_count"], 2)
        self.assertEqual(len(pool.connection.attempts), 2)
        self.assertEqual([a["attempt_number"] for a in pool.connection.attempts], [1, 2])
        self.assertEqual(acknowledged["status"], "acknowledged")
        self.assertIsNotNone(acknowledged["acknowledged_at"])
        self.assertEqual(acknowledged_again["status"], "acknowledged")
        self.assertEqual(len(pool.connection.attempts), 2)

    def test_repeated_delivery_after_sent_does_not_create_a_third_attempt(self):
        async def exercise():
            pool = _Pool()
            with patch.dict(os.environ, {
                "ALERT_DELIVERY_ENABLED": "true",
                "ALERT_WEBHOOK_URL": "https://example.invalid/webhook",
            }, clear=False), patch("app.module5b._post_webhook", return_value=(True, 202, None)):
                first = await deliver_alert(pool, pool.connection.alert["alert_id"])
                second = await deliver_alert(pool, pool.connection.alert["alert_id"])
            return pool, first, second

        pool, first, second = asyncio.run(exercise())
        self.assertEqual(first["status"], "sent")
        self.assertEqual(second["status"], "sent")
        self.assertFalse(second["dry_run"])
        self.assertEqual(len(pool.connection.attempts), 1)


if __name__ == "__main__":
    unittest.main()
