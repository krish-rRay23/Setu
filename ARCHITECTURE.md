# Setu — System Architecture & Design Specification

Setu is a ledger-safe, bounded-autonomy AI agent designed for automated payment failure diagnosis and revenue recovery via Razorpay APIs.

---

## 1. The Three-Component Architecture

Setu avoids non-deterministic multi-agent loops by enforcing a strict 3-component pipeline:

```
[ Webhook Ingestion ] ──> (1) Classifier ──> (2) Policy Engine ──> (3) Ledger-Executor ──> [ Razorpay API ]
```

### Component 1: Classifier (`src/classifier/`)
- **[src/classifier/rules.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/classifier/rules.py)**: Deterministic lookup table mapping ~70% of unambiguous Razorpay error codes (`BAD_REQUEST_PAYMENT_CARD_EXPIRED`, `BAD_REQUEST_PAYMENT_OTP_TIMEOUT`, `BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS`, `GATEWAY_ERROR_BANK_TIMED_OUT`) with `confidence = 1.0`.
- **[src/classifier/llm.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/classifier/llm.py)**: Invoked **only** when `rules_classifier` returns `None`. Processes pruned structured signals (error code, attempt velocity, bank downtime correlation) and outputs a JSON schema: `{category, confidence, evidence, abstain}`.
- **[src/classifier/models.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/classifier/models.py)**: Defines fixed root-cause enum: `BANK_TRANSIENT`, `INSUFFICIENT_FUNDS`, `RISK_BLOCK`, `CUSTOMER_ABANDONMENT`, `SESSION_EXPIRED`, `UNKNOWN`.

### Component 2: Policy Engine (`src/policy/`)
- **[src/policy/engine.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/policy/engine.py)**: Pure, deterministic function (`decide_action`) with **NO LLM calls** and **NO external API calls**.
- **[src/policy/config.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/policy/config.py)**: `PolicyThresholdConfig` centralizes all thresholds:
  - Max retries cap: 3 retries
  - Escalation amount: ₹50,000 (5,000,000 paise)
  - Minimum confidence: 0.70
  - Insufficient funds cooldown: 24.0 hours
  - Bank transient base backoff: 300 seconds
- Maps input context to an explicit `Action`: `RETRY_NOW`, `RETRY_SCHEDULED(delay)`, `NUDGE_CUSTOMER`, `ESCALATE_HUMAN`, `WRITE_OFF`.

### Component 3: Ledger-Executor (`src/ledger/` & `src/executor/`)
- **[src/ledger/models.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/ledger/models.py)**: Append-only `ledger_events` table with database-level `UniqueConstraint("idempotency_key")`.
- **[src/ledger/executor.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/ledger/executor.py)**:
  - `record_and_execute(action)`: Writes a `pending` row to DB **FIRST** inside a transaction. DB constraint rejects duplicate attempts (`IntegrityError`). Only then calls action executor.
  - `reconcile_pending()`: On startup, verifies pending rows against remote status checks before taking action—never blindly re-executing.
- **[src/executor/razorpay_client.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/executor/razorpay_client.py)**: Creates Razorpay Payment Links (`POST /v1/payment_links`) tagged with `reference_id = idempotency_key`.
- **[src/executor/webhook.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/executor/webhook.py)**: HMAC SHA-256 signature verification (`verify_webhook_signature`) and event normalizer (`normalize_webhook_event`).

---

## 2. End-to-End Agent Loop

The full execution flow is orchestrated by **[src/executor/pipeline.py](file:///c:/Users/krish/OneDrive/Desktop/Setu/src/executor/pipeline.py)**:

1. **Observe**: Ingest incoming Razorpay `payment.failed`, `subscription.charged.failed`, or `payout.failed` webhook. Verify HMAC-SHA256 signature.
2. **Reason**: Pass event to `classify_event()`. If unambiguous rule matches, return immediately (`source='rules'`). Otherwise, pass pruned signals to `llm_classifier()`.
3. **Decide**: Pass classification to `decide_action()`. Enforce monetary caps, retry limits, and safe fallbacks for low confidence / abstention.
4. **Act**: Compute `idempotency_key = sha256(order_id, attempt_number)`. Commit `pending` ledger entry to DB **FIRST**. Execute Razorpay API call to generate Payment Link.
5. **Verify**: Update ledger entry to `confirmed` or `failed` with response evidence.

---

## 3. Invariants & Guarantees

- **Zero Duplicate Charges (0.0%)**: Guaranteed by database `UniqueConstraint` on `idempotency_key`.
- **Write-Ahead Logging**: Ledger row is committed before external network calls occur.
- **Honest Abstention**: When confidence is low (<0.70) or context is sparse, `llm_classifier` returns `abstain=True`, routing to non-aggressive action (`NUDGE_CUSTOMER` or `ESCALATE_HUMAN`).
