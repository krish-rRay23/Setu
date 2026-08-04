import unittest

def calculate_backoff_seconds(attempt, base_sec=2, max_sec=60):
    delay = base_sec * (2 ** (attempt - 1))
    return min(delay, max_sec)

class TestPolicyBackoff(unittest.TestCase):
    def test_backoff(self):
        self.assertEqual(calculate_backoff_seconds(1), 2)
        self.assertEqual(calculate_backoff_seconds(2), 4)
        self.assertEqual(calculate_backoff_seconds(3), 8)
        self.assertEqual(calculate_backoff_seconds(10), 60)
