import unittest
import time

def is_webhook_fresh(webhook_timestamp, tolerance_seconds=300):
    now = int(time.time())
    return abs(now - webhook_timestamp) <= tolerance_seconds

class TestWebhookTolerance(unittest.TestCase):
    def test_freshness(self):
        now = int(time.time())
        self.assertTrue(is_webhook_fresh(now - 60))
        self.assertFalse(is_webhook_fresh(now - 600))
