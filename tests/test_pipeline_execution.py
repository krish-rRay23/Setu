import unittest
from src.classifier.models import RootCauseCategory
from src.classifier.rules import rules_classifier
from src.policy.engine import decide_action
from src.policy.models import ActionType

class TestPipelineExecution(unittest.TestCase):
    def test_pipeline_decision_flow(self):
        # 1. Incoming failed event
        event = {
            'payment_id': 'pay_999',
            'order_id': 'order_999',
            'amount': 150000,
            'error_code': 'BAD_REQUEST_PAYMENT_OTP_TIMEOUT'
        }
        # 2. Classify
        classification = rules_classifier(event)
        self.assertIsNotNone(classification)
        self.assertEqual(classification.category, RootCauseCategory.CUSTOMER_ABANDONMENT)

        # 3. Policy decide
        action = decide_action(
            classification=classification,
            attempt_count=1,
            elapsed_time_since_first_attempt=0,
            amount=event['amount']
        )
        self.assertEqual(action.type, ActionType.NUDGE_CUSTOMER)

if __name__ == '__main__':
    unittest.main()
