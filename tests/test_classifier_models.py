import unittest
from src.classifier.models import RootCauseCategory, ClassificationResult

class TestClassifierModels(unittest.TestCase):
    def test_root_cause_categories_exist(self):
        expected = {
            'BANK_TRANSIENT', 'INSUFFICIENT_FUNDS', 'RISK_BLOCK',
            'CUSTOMER_ABANDONMENT', 'SESSION_EXPIRED', 'UNKNOWN'
        }
        actual = {c.value for c in RootCauseCategory}
        self.assertEqual(expected, actual)

    def test_classification_result_to_dict(self):
        res = ClassificationResult(
            category=RootCauseCategory.BANK_TRANSIENT,
            confidence=0.95,
            evidence=['error_code: GATEWAY_ERROR_BANK_TIMED_OUT'],
            abstain=False,
            source='rules'
        )
        d = res.to_dict()
        self.assertEqual(d['category'], 'BANK_TRANSIENT')
        self.assertEqual(d['confidence'], 0.95)
        self.assertEqual(d['evidence'], ['error_code: GATEWAY_ERROR_BANK_TIMED_OUT'])
        self.assertFalse(d['abstain'])
        self.assertEqual(d['source'], 'rules')

if __name__ == '__main__':
    unittest.main()
