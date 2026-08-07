import unittest
from src.ledger.db import init_db, get_session_factory
from src.ledger.executor import compute_idempotency_key, record_and_execute

class TestLedgerExecutor(unittest.TestCase):
    def setUp(self):
        engine = init_db(db_url='sqlite:///:memory:')
        self.session_factory = get_session_factory(engine)

    def test_compute_idempotency_key(self):
        k1 = compute_idempotency_key('order_1', 1)
        k2 = compute_idempotency_key('order_1', 1)
        k3 = compute_idempotency_key('order_1', 2)
        self.assertEqual(k1, k2)
        self.assertNotEqual(k1, k3)

    def test_record_and_execute(self):
        action = {
            'order_id': 'order_100',
            'attempt_number': 1,
            'action_type': 'RETRY_SCHEDULED',
            'evidence_json': {'source': 'test'}
        }
        res = record_and_execute(action, self.session_factory)
        self.assertTrue(res['executed'])
        self.assertEqual(res['status'], 'confirmed')

if __name__ == '__main__':
    unittest.main()
