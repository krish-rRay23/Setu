import unittest

def is_line_length_valid(line, max_len=120):
    return len(line) <= max_len

class TestLintConfig(unittest.TestCase):
    def test_line_length(self):
        self.assertTrue(is_line_length_valid("short line"))
        self.assertFalse(is_line_length_valid("x" * 121))
