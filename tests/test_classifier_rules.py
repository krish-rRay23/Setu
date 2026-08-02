import unittest
from src.classifier.rules import rules_classifier
from src.classifier.models import RootCauseCategory

class TestClassifierRules(unittest.TestCase):
    def test_bank_transient_rules(self):
        res = rules_classifier({'error_code': 'GATEWAY_ERROR_BANK_TIMED_OUT'})
        self.assertIsNotNone(res)
        self.assertEqual(res.category, RootCauseCategory.BANK_TRANSIENT)
        self.assertEqual(res.confidence, 1.0)

    def test_insufficient_funds_rules(self):
        res = rules_classifier({'error_code': 'BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS'})
        self.assertIsNotNone(res)
        self.assertEqual(res.category, RootCauseCategory.INSUFFICIENT_FUNDS)

    def test_ambiguous_error_escalates_to_llm(self):
        res = rules_classifier({'error_code': 'payment_failed'})
        self.assertIsNone(res)

if __name__ == '__main__':
    unittest.main()
