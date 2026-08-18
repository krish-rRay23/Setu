# Setu Operational Runbook

## Overview
Setu operates as an automated recovery agent for Razorpay failed transactions with bounded autonomy and idempotent ledger safety.

## Triage Procedure
1. Verify Webhook Signature via HMAC SHA-256.
2. Route root-cause classification through deterministic error rules first.
3. Fallback to Gemini 2.5 Flash for ambiguous failure codes.
4. Execute strictly bounded policy action (Retry, Nudge, Write-off, Human Escalate).
5. Ensure write-ahead idempotent lock in SQLite ledger before dispatching external calls.
