import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

# Ensure root workspace is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ledger.db import init_db, get_session_factory
from src.ledger.models import LedgerEvent
from src.ledger.executor import (
    record_and_execute,
    reconcile_pending,
    compute_idempotency_key,
)


def run_crash_injection_tests():
    print("=" * 70)
    print("        SETU LEDGER-EXECUTOR CRASH INJECTION & SAFETY SUITE       ")
    print("=" * 70)

    db_path = "sqlite:///demo_ledger.db"
    if os.path.exists("demo_ledger.db"):
        os.remove("demo_ledger.db")

    engine = init_db(db_url=db_path)
    session_factory = get_session_factory(engine)

    pass_results = []

    # =========================================================================
    # SCENARIO 1: N Concurrent Attempts for SAME (order_id, attempt_number)
    # =========================================================================
    print("\n[SCENARIO 1] Testing N Concurrent Attempts to record SAME (order_id, attempt_number)...")
    
    order_id_1 = "ord_concurrent_1001"
    attempt_1 = 1
    action_1 = {
        "order_id": order_id_1,
        "attempt_number": attempt_1,
        "action_type": "retry_now",
        "evidence_json": {"reason": "insufficient_funds_transient"},
    }

    executor_calls = 0
    executor_lock = threading.Lock()

    def tracking_executor(act):
        nonlocal executor_calls
        with executor_lock:
            executor_calls += 1
        time.sleep(0.05)  # Simulate API latency
        return {
            "success": True,
            "transaction_id": "pay_test_999",
            "message": "Payment captured",
        }

    num_threads = 10
    results = []

    with ThreadPoolExecutor(max_workers=num_threads) as pool:
        futures = [
            pool.submit(
                record_and_execute, action_1, session_factory, tracking_executor
            )
            for _ in range(num_threads)
        ]
        for f in as_completed(futures):
            results.append(f.result())

    # Assertions for Scenario 1
    session = session_factory()
    db_rows = session.query(LedgerEvent).filter_by(order_id=order_id_1).all()
    session.close()

    successful_executions = [r for r in results if not r["duplicate"] and r["executed"]]
    blocked_duplicates = [r for r in results if r["duplicate"]]

    print(f"  - Concurrent threads spawned: {num_threads}")
    print(f"  - Ledger rows created in DB: {len(db_rows)}")
    print(f"  - Executor function executions: {executor_calls}")
    print(f"  - Threads with successful execution: {len(successful_executions)}")
    print(f"  - Threads rejected by DB Unique Constraint: {len(blocked_duplicates)}")

    s1_pass = (
        len(db_rows) == 1
        and executor_calls == 1
        and len(successful_executions) == 1
        and len(blocked_duplicates) == (num_threads - 1)
    )

    if s1_pass:
        print("  --> RESULT: PASS (Only 1 ledger row created, DB constraint rejected all duplicates, executor ran exactly ONCE)")
        pass_results.append(("Scenario 1: Concurrent Execution Prevention", True))
    else:
        print("  --> RESULT: FAIL")
        pass_results.append(("Scenario 1: Concurrent Execution Prevention", False))

    # =========================================================================
    # SCENARIO 2: Crash Simulation Mid-Retry & Restart Recovery Reconciliation
    # =========================================================================
    print("\n[SCENARIO 2] Testing Process Crash & Startup Recovery Reconciliation...")

    order_id_2 = "ord_crash_2002"
    attempt_2 = 1
    idempotency_key_2 = compute_idempotency_key(order_id_2, attempt_2)

    # 1. Simulate process crash by writing a raw 'pending' row directly into DB
    #    (as if process crashed right after write-ahead pending commit before executor call)
    print("  - Simulating process crash: Writing 'pending' write-ahead entry to DB...")
    session = session_factory()
    pending_row = LedgerEvent(
        idempotency_key=idempotency_key_2,
        order_id=order_id_2,
        attempt_number=attempt_2,
        action_type="retry_now",
        status="pending",
        evidence_json={"crash_test": True},
    )
    session.add(pending_row)
    session.commit()
    session.close()

    # Reset executor call counter to verify executor is NOT called blindly
    reconcile_executor_calls = 0

    def fail_if_executed(act):
        nonlocal reconcile_executor_calls
        reconcile_executor_calls += 1
        return {"success": True}

    status_check_calls = 0

    def custom_status_check(ord_id, att_num):
        nonlocal status_check_calls
        status_check_calls += 1
        return {
            "executed": True,
            "status": "confirmed",
            "order_id": ord_id,
            "attempt_number": att_num,
            "details": "Remote Razorpay status verified: payment succeeded prior to process termination.",
        }

    # 2. Simulate process restart by calling reconcile_pending()
    print("  - Simulating system restart: Calling reconcile_pending()...")
    reconciled = reconcile_pending(session_factory, status_check_fn=custom_status_check)

    session = session_factory()
    reconciled_db_row = session.query(LedgerEvent).filter_by(order_id=order_id_2).first()
    session.close()

    print(f"  - Pending rows reconciled: {len(reconciled)}")
    print(f"  - Status check function invocations: {status_check_calls}")
    print(f"  - Executor re-executions triggered: {reconcile_executor_calls}")
    print(f"  - Reconciled DB row status: {reconciled_db_row.status if reconciled_db_row else 'None'}")

    s2_pass = (
        len(reconciled) == 1
        and status_check_calls == 1
        and reconcile_executor_calls == 0
        and reconciled_db_row is not None
        and reconciled_db_row.status == "confirmed"
    )

    if s2_pass:
        print("  --> RESULT: PASS (Pending row reconciled via remote status check; ZERO blind re-executions occurred)")
        pass_results.append(("Scenario 2: Crash Recovery Reconciliation", True))
    else:
        print("  --> RESULT: FAIL")
        pass_results.append(("Scenario 2: Crash Recovery Reconciliation", False))

    # =========================================================================
    # SCENARIO 3: Duplicate Webhook Delivery for Same Event
    # =========================================================================
    print("\n[SCENARIO 3] Testing Duplicate Webhook Delivery for Same Event...")

    order_id_3 = "ord_webhook_3003"
    attempt_3 = 1
    webhook_action = {
        "order_id": order_id_3,
        "attempt_number": attempt_3,
        "action_type": "nudge_customer",
        "evidence_json": {"webhook_id": "evt_wh_abc123"},
    }

    webhook_executor_calls = 0

    def webhook_executor(act):
        nonlocal webhook_executor_calls
        webhook_executor_calls += 1
        return {"success": True, "nudge_sent": True}

    # First webhook delivery
    print("  - Initial webhook delivery: Calling record_and_execute()...")
    res1 = record_and_execute(webhook_action, session_factory, webhook_executor)
    print(f"    Delivery 1 outcome -> duplicate: {res1['duplicate']}, executed: {res1['executed']}, status: {res1['status']}")

    # Second webhook delivery (duplicate)
    print("  - Duplicate webhook delivery: Calling record_and_execute() again with exact same (order_id, attempt_number)...")
    res2 = record_and_execute(webhook_action, session_factory, webhook_executor)
    print(f"    Delivery 2 outcome -> duplicate: {res2['duplicate']}, executed: {res2['executed']}, status: {res2['status']}")

    session = session_factory()
    webhook_db_rows = session.query(LedgerEvent).filter_by(order_id=order_id_3).all()
    session.close()

    print(f"  - Ledger rows in DB for order: {len(webhook_db_rows)}")
    print(f"  - Action executor total executions: {webhook_executor_calls}")

    s3_pass = (
        not res1["duplicate"]
        and res1["executed"]
        and res2["duplicate"]
        and not res2["executed"]
        and len(webhook_db_rows) == 1
        and webhook_executor_calls == 1
    )

    if s3_pass:
        print("  --> RESULT: PASS (Duplicate webhook resulted in clean no-op without re-executing action)")
        pass_results.append(("Scenario 3: Duplicate Webhook Idempotency", True))
    else:
        print("  --> RESULT: FAIL")
        pass_results.append(("Scenario 3: Duplicate Webhook Idempotency", False))

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("                      SUMMARY OF TEST SCENARIOS                    ")
    print("=" * 70)
    all_passed = True
    for name, passed in pass_results:
        status_str = "PASS" if passed else "FAIL"
        print(f"  [{status_str}] {name}")
        if not passed:
            all_passed = False

    print("=" * 70)
    if all_passed:
        print("OVERALL RESULT: ALL SCENARIOS PASSED PERFECTLY!")
    else:
        print("OVERALL RESULT: ONE OR MORE SCENARIOS FAILED!")
    print("=" * 70)

    # Cleanup demo db file
    engine.dispose()
    if os.path.exists("demo_ledger.db"):
        os.remove("demo_ledger.db")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_crash_injection_tests())
