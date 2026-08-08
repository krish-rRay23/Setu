import unittest
import hmac, hashlib
from src.executor.webhook import verify_webhook_signature, normalize_webhook_event

class TestWebhookParser(unittest.TestCase):
    def test_signature_verification(self):
        secret = 'test_webhook_secret'
        body = '{"event":"payment.failed"}'
        sig = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
        self.assertTrue(verify_webhook_signature(body, sig, secret))
        self.assertFalse(verify_webhook_signature(body, 'invalid_sig', secret))

    def test_normalize_webhook_event(self):
        payload = {
            'event': 'payment.failed',
            'payload': {
                'payment': {
                    'entity': {
                        'id': 'pay_123',
                        'order_id': 'order_123',
                        'amount': 250000,
                        'error_code': 'BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS'
                    }
                }
            }
        }
        event = normalize_webhook_event(payload)
        self.assertEqual(event['order_id'], 'order_123')
        self.assertEqual(event['amount'], 250000)

if __name__ == '__main__':
    unittest.main()
