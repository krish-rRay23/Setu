import unittest
import os
from src.config_validator import validate_environment

class TestConfigValidator(unittest.TestCase):
    def test_missing_environment_keys(self):
        old_id = os.environ.pop("RAZORPAY_KEY_ID", None)
        old_sec = os.environ.pop("RAZORPAY_KEY_SECRET", None)
        try:
            res = validate_environment()
            self.assertFalse(res["valid"])
            self.assertIn("RAZORPAY_KEY_ID", res["missing"])
        finally:
            if old_id: os.environ["RAZORPAY_KEY_ID"] = old_id
            if old_sec: os.environ["RAZORPAY_KEY_SECRET"] = old_sec

if __name__ == '__main__':
    unittest.main()
