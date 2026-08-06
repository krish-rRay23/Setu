import unittest
from src.ledger.models import LedgerEvent

class TestLedgerModels(unittest.TestCase):
    def test_ledger_event_initialization(self):
        ev = LedgerEvent(
            idempotency_key='order_test_123_1',
            order_id='order_test_123',
            attempt_number=1,
            action_type='RETRY_SCHEDULED',
            status='pending',
            evidence_json={'reason': 'bank timeout'}
        )
        d = ev.to_dict()
        self.assertEqual(d['idempotency_key'], 'order_test_123_1')
        self.assertEqual(d['order_id'], 'order_test_123')
        self.assertEqual(d['status'], 'pending')

if __name__ == '__main__':
    unittest.main()
