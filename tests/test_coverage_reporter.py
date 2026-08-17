import unittest

def format_coverage_summary(passed, total):
    pct = (passed / total) * 100.0 if total > 0 else 0.0
    return f"{passed}/{total} tests passed ({pct:.1f}%)"

class TestCoverageReporter(unittest.TestCase):
    def test_summary(self):
        s = format_coverage_summary(25, 25)
        self.assertEqual(s, "25/25 tests passed (100.0%)")
