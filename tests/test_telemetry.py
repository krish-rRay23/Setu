import unittest
import json
from src.telemetry import AuditLogger

class TestTelemetry(unittest.TestCase):
    def test_audit_logger_sanitization(self):
        logger = AuditLogger()
        output = logger.log_event("payment_processed", {
            "order_id": "order_123",
            "card_number": "4111111111111111",
            "amount": 50000
        })
        parsed = json.loads(output)
        self.assertEqual(parsed["payload"]["order_id"], "order_123")
        self.assertEqual(parsed["payload"]["card_number"], "[REDACTED]")
        self.assertEqual(parsed["payload"]["amount"], 50000)

if __name__ == '__main__':
    unittest.main()
