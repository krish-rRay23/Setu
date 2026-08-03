import unittest
from src.classifier.llm import _prune_context, default_mock_llm_inference

class TestClassifierLLM(unittest.TestCase):
    def test_prune_context(self):
        raw_event = {
            'error_code': 'payment_failed',
            'error_description': 'Internal server error at gateway',
            'amount': 250000,
            'bank': 'HDFC'
        }
        pruned = _prune_context(raw_event, {'timing_pattern': 'burst'})
        self.assertEqual(pruned['error_code'], 'payment_failed')
        self.assertEqual(pruned['timing_pattern'], 'burst')
        self.assertEqual(pruned['amount'], 250000)

    def test_mock_llm_inference(self):
        pruned = {'error_code': 'payment_failed', 'repeat_attempt_count': 1, 'recent_bank_failure_rate': 0.8}
        res = default_mock_llm_inference(pruned)
        self.assertIn('category', res)
        self.assertEqual(res['category'], 'BANK_TRANSIENT')

if __name__ == '__main__':
    unittest.main()
