# Setu — Project Brief (persistent context — read this every session)

## What this is
A ledger-safe, bounded-autonomy agent that diagnoses why a Razorpay
payment/subscription-charge/payout actually failed, then executes ONE
of a small fixed set of recovery actions through Razorpay's real
test-mode APIs — with a guarantee, proven by a live crash-injection
test, that it can never double-charge a customer.

Target: Razorpay AI Buildathon 2026, Track 3 (AI Revenue Recovery).

## The three components (do not add more — no multi-agent theater)
1. **Classifier** — deterministic rule table for unambiguous failure
   codes (~70% of cases) + a confidence-scored LLM/ML classifier for
   the ambiguous residual (~30%). Rules run first, always. LLM is
   only invoked when rules can't resolve the case.
2. **Policy** — pure deterministic function. Maps
   (root_cause_category, confidence, attempt_count, elapsed_time,
   amount) -> one of {retry_now, retry_scheduled, nudge_customer,
   escalate_human, write_off}. Low confidence ALWAYS routes to the
   safest action, never the most aggressive. Hard caps: max 3
   automated retries per transaction, cooldown after "insufficient
   funds," mandatory escalation above a configurable rupee threshold.
   No LLM involvement in this component at all.
3. **Ledger-Executor** — event-sourced, append-only ledger. Every
   action is keyed by an idempotency key derived from
   hash(order_id, attempt_number) — NOT from timing. Ledger write
   happens BEFORE any external API call (write-ahead). Enforce
   uniqueness at the database level (unique constraint on the
   idempotency key), not just in application code. On restart, any
   "pending" ledger entry is re-verified against actual Razorpay
   transaction state before any further action — never blindly
   re-executed.

## Agent loop
observe (webhook event) -> reason (Classifier) -> decide (Policy)
-> act (Executor, real Razorpay test-mode API) -> verify (poll /
webhook-confirm outcome) -> stop/escalate (hard caps, audit log)

## Non-negotiable invariants (never violate these, ever, in any phase)
- Duplicate-charge rate must be exactly 0%, provably, under: crash
  mid-retry, duplicate webhook delivery (Razorpay webhooks are
  documented at-least-once), and concurrent execution.
- Every single action (attempted or taken) is logged with: input
  evidence, classifier output + confidence, policy action chosen,
  executor result, timestamp. No silent actions.
- Never charge an amount different from the original order.
- Test-mode Razorpay API keys only. Never real keys, never in git.

## What "done" looks like per phase
See the phase prompts. Each phase ends with a checkpoint summary
before the next phase starts.

## What I (the human) decide, not you (the agent)
- The idempotency key scheme and write-ahead ordering
- The policy thresholds, caps, and cooldown windows
- The ground-truth label design for synthetic eval data
- What gets removed for each ablation and why
- How abstention / "insufficient evidence" cases are reported
If any of these come up mid-task, stop and ask rather than picking
a default.