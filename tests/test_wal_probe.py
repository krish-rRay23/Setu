import unittest

def parse_pragma_journal_mode(row_result):
    return str(row_result).strip().lower() == "wal"

class TestWALProbe(unittest.TestCase):
    def test_wal(self):
        self.assertTrue(parse_pragma_journal_mode("wal"))
        self.assertFalse(parse_pragma_journal_mode("delete"))
