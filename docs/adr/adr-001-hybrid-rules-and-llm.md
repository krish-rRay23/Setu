# ADR 001: Hybrid Rules + LLM Architecture Over LLM-Only Classification

## Context & Problem Statement
In automated payment recovery, roughly 70% of payment failures stem from known, unambiguous Razorpay error codes (e.g., `BAD_REQUEST_PAYMENT_CARD_EXPIRED`, `BAD_REQUEST_PAYMENT_OTP_TIMEOUT`, `BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS`). Relying exclusively on an LLM for all error classifications introduces unnecessary latency, financial API cost, non-determinism, and vulnerability to hallucinations on standard error codes.

## Decision Drivers
- **Latency & Throughput**: Known error codes must be processed in under 1 millisecond.
- **Deterministic Reliability**: Standard error codes must map 100% reliably to root causes without model variance.
- **Cost & Efficiency**: Avoid invoking LLMs for high-volume, routine payment failures.
- **Handling Residual Ambiguity**: The remaining ~30% of ambiguous errors (`payment_failed`, `GATEWAY_ERROR`) require reasoning over context signals (bank failure rates, attempt velocity).

## Decision
We adopt a **dual-stage Classifier architecture**:
1. `rules_classifier(event)` runs first as a pure lookup table for unambiguous error codes with `confidence = 1.0`.
2. `llm_classifier(event, context)` is invoked **only** if `rules_classifier` returns `None`.

## Consequences
- **Positive**: 70% of events resolve deterministically in <0.01ms with zero LLM API cost.
- **Positive**: Ambiguous cases trigger structured LLM reasoning with an explicit JSON schema (`{category, confidence, evidence, abstain}`).
- **Positive**: Honest abstention (`abstain=True`) is natively supported when confidence is low (<0.70).
