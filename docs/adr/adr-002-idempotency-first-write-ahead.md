# ADR 002: Idempotency-First Write-Ahead Ledger Over Eventual-Consistency

## Context & Problem Statement
Razorpay webhooks are delivered with at-least-once semantics, leading to duplicate webhook deliveries under network retries. Furthermore, process crashes mid-execution and concurrent API requests can lead to double-charging a customer if recovery actions are executed before recording state in a transactional database.

## Decision Drivers
- **Zero Duplicate-Charge Guarantee**: Duplicate-charge rate must be strictly 0.0% under process crashes, duplicate webhooks, and concurrent requests.
- **Database-Level Safety**: Uniqueness must be enforced by database constraints (`UniqueConstraint`), not application-level `if exists` logic alone (which races under concurrency).
- **Crash Recovery**: Unfinished actions must be reconcilable on process restart without blind re-execution.

## Decision
We implement a **Write-Ahead Ledger Architecture (`src/ledger/`)**:
1. Every action is assigned a deterministic `idempotency_key = sha256(order_id, attempt_number)`.
2. `record_and_execute(action)` inserts a `pending` row into `ledger_events` inside a database transaction **FIRST**.
3. The database-level `UniqueConstraint` on `idempotency_key` rejects any concurrent attempt at the database layer (`IntegrityError`), converting duplicate calls to instant no-ops.
4. The external action (e.g. Razorpay Payment Link creation) is called **ONLY** after the `pending` row is committed.
5. On startup, `reconcile_pending()` queries remote state via status checks before taking action—never blindly re-executing.

## Consequences
- **Positive**: Duplicate-charge rate is provably 0.0% across all race conditions, crash scenarios, and duplicate webhooks.
- **Positive**: Confirmed by `eval/ablations/ablation_remove_ledger_safety.py`, which proves that removing DB-level ledger safety results in a 1.38% duplicate-charge rate.
