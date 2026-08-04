import unittest
from src.policy.models import ActionType, Action
from src.policy.config import PolicyThresholdConfig

class TestPolicyModels(unittest.TestCase):
    def test_action_types_defined(self):
        expected = {'RETRY_NOW', 'RETRY_SCHEDULED', 'NUDGE_CUSTOMER', 'ESCALATE_HUMAN', 'WRITE_OFF'}
        actual = {a.value for a in ActionType}
        self.assertEqual(expected, actual)

    def test_action_serialization(self):
        action = Action(type=ActionType.RETRY_SCHEDULED, delay_seconds=300, reason='Transient bank error')
        d = action.to_dict()
        self.assertEqual(d['type'], 'RETRY_SCHEDULED')
        self.assertEqual(d['delay_seconds'], 300)
        self.assertEqual(d['reason'], 'Transient bank error')

    def test_policy_threshold_config_defaults(self):
        cfg = PolicyThresholdConfig()
        self.assertEqual(cfg.max_retries, 3)
        self.assertEqual(cfg.escalation_amount, 5000000)
        self.assertAlmostEqual(cfg.min_confidence, 0.70)

if __name__ == '__main__':
    unittest.main()
