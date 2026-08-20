import sys
import os
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from sqlalchemy import create_engine, Column, Integer, String, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

UnsafeBase = declarative_base()


class UnsafeLedgerEvent(UnsafeBase):
    """
    Unsafe Ledger table WITHOUT a UNIQUE constraint on idempotency_key.
    Simulates what happens if database-level uniqueness enforcement is omitted.
    """

    __tablename__ = "unsafe_ledger_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    idempotency_key = Column(String(64), nullable=True)  # NO UNIQUE CONSTRAINT!
    order_id = Column(String(100), nullable=False)
    attempt_number = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False)


def unsafe_record_and_execute(action: dict, session_factory, executor_fn) -> dict:
    """
    Unsafe execution flow WITHOUT database-level unique constraint protection.
    Relies purely on application-level checks (which race under concurrency)
    or executes action BEFORE writing to DB.
    """
    order_id = action["order_id"]
    attempt_number = action["attempt_number"]
    idempotency_key = f"{order_id}_{attempt_number}"

    session = session_factory()
    # Application-level check (vulnerable to race condition under concurrency!)
    existing = (
        session.query(UnsafeLedgerEvent)
        .filter_by(idempotency_key=idempotency_key)
        .first()
    )
    if existing:
        session.close()
        return {"duplicate": True, "executed": False}

    session.close()

    # Call executor WITHOUT write-ahead database locking or unique constraint
    result = executor_fn(action)

    # Insert row AFTER executor call (no write-ahead protection)
    session = session_factory()
    event = UnsafeLedgerEvent(
        idempotency_key=idempotency_key,
        order_id=order_id,
        attempt_number=attempt_number,
        status="confirmed",
    )
    session.add(event)
    session.commit()
    session.close()

    return {"duplicate": False, "executed": True}


def run_remove_ledger_safety_ablation_test():
    print("=" * 80)
    print("   ABLATION: REMOVE LEDGER SAFETY (WITHOUT DB UNIQUE CONSTRAINT) TEST   ")
    print("=" * 80)

    db_path = "sqlite:///unsafe_ledger_demo.db"
    if os.path.exists("unsafe_ledger_demo.db"):
        os.remove("unsafe_ledger_demo.db")

    engine = create_engine(
        db_path, connect_args={"check_same_thread": False}, echo=False
    )
    UnsafeBase.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)

    order_id = "ord_unsafe_race_999"
    attempt = 1
    action = {"order_id": order_id, "attempt_number": attempt}

    executor_calls = 0
    executor_lock = threading.Lock()

    def tracking_executor(act):
        nonlocal executor_calls
        with executor_lock:
            executor_calls += 1
        time.sleep(0.05)  # Simulate network latency
        return {"success": True}

    num_threads = 10
    results = []

    print(
        f"Firing {num_threads} concurrent attempts for SAME order without DB unique constraint..."
    )
    with ThreadPoolExecutor(max_workers=num_threads) as pool:
        futures = [
            pool.submit(
                unsafe_record_and_execute,
                action,
                session_factory,
                tracking_executor,
            )
            for _ in range(num_threads)
        ]
        for f in as_completed(futures):
            results.append(f.result())

    session = session_factory()
    db_rows = (
        session.query(UnsafeLedgerEvent).filter_by(order_id=order_id).all()
    )
    session.close()

    successful_executions = [r for r in results if r["executed"]]

    print(f"  - Ledger rows created in DB: {len(db_rows)}")
    print(f"  - Executor function executions: {executor_calls}")
    print(f"  - Successful executions: {len(successful_executions)}")

    engine.dispose()
    if os.path.exists("unsafe_ledger_demo.db"):
        os.remove("unsafe_ledger_demo.db")

    # In an unsafe system, race conditions cause MULTIPLE executions and MULTIPLE DB rows!
    has_duplicate_charges = executor_calls > 1 or len(db_rows) > 1

    if has_duplicate_charges:
        print("\n  [RESULT: PROVEN FAIL AS EXPECTED]")
        print(
            f"  --> DUPLICATE CHARGE DETECTED! Action executed {executor_calls} times across {len(db_rows)} DB rows."
        )
        print(
            "  --> Proves that without DB-level write-ahead unique constraint safety, duplicate charges DO occur!"
        )
        return True  # Proven fail
    else:
        print("\n  [RESULT: UNEXPECTED PASS]")
        return False


if __name__ == "__main__":
    run_remove_ledger_safety_ablation_test()
