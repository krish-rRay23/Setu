import unittest
from src.policy.engine import decide_action
from src.policy.models import ActionType
from src.policy.config import PolicyThresholdConfig
from src.classifier.models import ClassificationResult, RootCauseCategory

class TestPolicyEngine(unittest.TestCase):
    def setUp(self):
        self.config = PolicyThresholdConfig(max_retries=3, escalation_amount=5000000)

    def test_bank_transient_action(self):
        cls_result = ClassificationResult(
            category=RootCauseCategory.BANK_TRANSIENT,
            confidence=0.9,
            evidence=['gateway timeout']
        )
        action = decide_action(
            classification=cls_result,
            attempt_count=1,
            elapsed_time_since_first_attempt=0,
            amount=100000,
            threshold_config=self.config
        )
        self.assertEqual(action.type, ActionType.RETRY_SCHEDULED)

    def test_retry_cap_exhaustion_escalates(self):
        cls_result = ClassificationResult(
            category=RootCauseCategory.BANK_TRANSIENT,
            confidence=0.9,
            evidence=['gateway timeout']
        )
        action = decide_action(
            classification=cls_result,
            attempt_count=4,
            elapsed_time_since_first_attempt=1000,
            amount=100000,
            threshold_config=self.config
        )
        self.assertEqual(action.type, ActionType.ESCALATE_HUMAN)

if __name__ == '__main__':
    unittest.main()
