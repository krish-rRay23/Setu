import unittest

class WebhookDedup:
    def __init__(self):
        self.processed = set()

    def record(self, event_id):
        if event_id in self.processed:
            return False
        self.processed.add(event_id)
        return True

class TestWebhookDedup(unittest.TestCase):
    def test_dedup(self):
        d = WebhookDedup()
        self.assertTrue(d.record("evt_01"))
        self.assertFalse(d.record("evt_01"))
