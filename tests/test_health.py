import unittest
from src.health import check_system_health

class TestHealth(unittest.TestCase):
    def test_health_check_defaults(self):
        health = check_system_health()
        self.assertIn("status", health)
        self.assertEqual(health["components"]["classifier"], "ready")
        self.assertEqual(health["components"]["policy_engine"], "ready")

if __name__ == '__main__':
    unittest.main()
