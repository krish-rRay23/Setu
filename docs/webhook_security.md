# Webhook Security Architecture

1. Mandatory HMAC SHA-256 signature verification over raw request body.
2. Max 300-second timestamp drift allowed to prevent replay attacks.
3. Idempotent ledger insertion using unique `event_id`.
