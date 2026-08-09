import unittest
from unittest.mock import patch, MagicMock
from src.executor.razorpay_client import create_payment_link

class TestRazorpayClient(unittest.TestCase):
    @patch('requests.post')
    def test_create_payment_link(self, mock_post):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {'id': 'plink_123', 'short_url': 'https://rzp.io/i/test'}
        mock_post.return_value = mock_resp

        with patch.dict('os.environ', {'RAZORPAY_KEY_ID': 'key', 'RAZORPAY_KEY_SECRET': 'sec'}):
            res = create_payment_link(amount=50000, description='Retry Payment', idempotency_key='plink_idemp_1')
            self.assertEqual(res['id'], 'plink_123')

if __name__ == '__main__':
    unittest.main()
