# Webhook-to-Settlement Lifecycle

```
[Customer Payment Fails]
           │
           ▼
[Razorpay Webhook: payment.failed]
           │
           ▼
[Setu Webhook Parser & Signature Check]
           │
           ▼
[Hybrid Classifier: Rules -> Gemini Fallback]
           │
           ▼
[Policy Engine: Retry / Nudge / Escalate / Write-off]
           │
           ▼
[Ledger Safety: Write-Ahead Idempotent Commit]
           │
           ▼
[Action Executor: Razorpay Test-Mode API Dispatch]
```
