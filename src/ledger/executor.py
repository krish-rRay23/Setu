import hashlib
import logging
from typing import Callable, Optional, Dict, Any, List

from sqlalchemy.exc import IntegrityError
from src.ledger.models import LedgerEvent

logger = logging.getLogger("ledger_executor")
logger.setLevel(logging.INFO)


def compute_idempotency_key(order_id: str, attempt_number: int) -> str:
    """
    Computes a deterministic idempotency key as sha256(order_id, attempt_number).
    Guarantees unique key generation based on business identifiers.
    """
    raw_key = f"{order_id}:{attempt_number}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def fake_action_executor(action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Stub action executor that logs action details and returns execution result.
    """
    order_id = action.get("order_id")
    attempt_number = action.get("attempt_number")
    action_type = action.get("action_type")
    logger.info(
        f"[FAKE EXECUTOR] Executing action '{action_type}' for order={order_id}, attempt={attempt_number}"
    )
    return {
        "success": True,
        "action_type": action_type,
        "order_id": order_id,
        "attempt_number": attempt_number,
        "message": f"Successfully executed action {action_type} for order {order_id}",
    }


def fake_status_check(order_id: str, attempt_number: int) -> Dict[str, Any]:
    """
    Stub status check function to verify remote Razorpay transaction state
    for pending entries during recovery reconciliation.
    """
    logger.info(
        f"[FAKE STATUS CHECK] Verifying remote status for order={order_id}, attempt={attempt_number}"
    )
    return {
        "executed": True,
        "status": "confirmed",
        "order_id": order_id,
        "attempt_number": attempt_number,
        "details": "Verified via remote status check; transaction was completed.",
    }


def record_and_execute(
    action: Dict[str, Any],
    session_factory: Callable[[], Any],
    executor_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Core write-ahead execution pattern:
    1. Compute idempotency key.
    2. Write 'pending' row FIRST inside DB transaction. Unique constraint on idempotency_key
       is the database-level safety mechanism against duplicate execution.
    3. Call action executor ONLY after 'pending' row is committed.
    4. Update row to 'confirmed' or 'failed' based on executor outcome.
    """
    if executor_fn is None:
        executor_fn = fake_action_executor

    order_id = action["order_id"]
    attempt_number = action["attempt_number"]
    action_type = action["action_type"]
    evidence_json = action.get("evidence_json", {})

    idempotency_key = compute_idempotency_key(order_id, attempt_number)

    # Step 1: Write "pending" row FIRST (Write-Ahead Logging)
    session = session_factory()
    try:
        pending_event = LedgerEvent(
            idempotency_key=idempotency_key,
            order_id=order_id,
            attempt_number=attempt_number,
            action_type=action_type,
            status="pending",
            evidence_json=evidence_json,
        )
        session.add(pending_event)
        session.commit()
        event_id = pending_event.id
    except IntegrityError:
        session.rollback()
        # Enforced by DB Unique Constraint!
        existing = (
            session.query(LedgerEvent)
            .filter_by(idempotency_key=idempotency_key)
            .first()
        )
        res = existing.to_dict() if existing else None
        session.close()
        logger.info(
            f"[LEDGER] Duplicate attempt blocked by DB constraint for idempotency_key={idempotency_key}"
        )
        return {
            "duplicate": True,
            "executed": False,
            "event": res,
            "status": res["status"] if res else "unknown",
        }
    finally:
        session.close()

    # Step 2: Call executor ONLY after pending row is safely in DB
    try:
        result = executor_fn(action)
        success = result.get("success", True)
        new_status = "confirmed" if success else "failed"
        updated_evidence = {**evidence_json, "executor_result": result}
    except Exception as e:
        logger.error(f"[EXECUTOR ERROR] Action execution failed: {e}")
        new_status = "failed"
        updated_evidence = {**evidence_json, "error": str(e)}

    # Step 3: Update row status to confirmed or failed
    session = session_factory()
    try:
        event = session.query(LedgerEvent).filter_by(id=event_id).first()
        if event:
            event.status = new_status
            event.evidence_json = updated_evidence
            session.commit()
            return {
                "duplicate": False,
                "executed": True,
                "event": event.to_dict(),
                "status": new_status,
            }
        else:
            return {
                "duplicate": False,
                "executed": True,
                "event": None,
                "status": new_status,
            }
    finally:
        session.close()


def reconcile_pending(
    session_factory: Callable[[], Any],
    status_check_fn: Optional[Callable[[str, int], Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    """
    Startup recovery function:
    Finds all 'pending' rows in ledger_events and re-verifies them against the
    remote status check function before taking any action — never blindly re-executes.
    """
    session = session_factory()
    try:
        pending_rows = (
            session.query(LedgerEvent).filter_by(status="pending").all()
        )
        reconciled_events = []

        for row in pending_rows:
            logger.info(
                f"[RECONCILE] Found pending row id={row.id}, order_id={row.order_id}, attempt={row.attempt_number}, key={row.idempotency_key[:16]}..."
            )
            if status_check_fn is not None:
                verification = status_check_fn(row.order_id, row.attempt_number)
            else:
                # Live Razorpay remote status check lookup by idempotency_key
                from src.executor.razorpay_client import fetch_payment_link_by_reference_id
                remote = fetch_payment_link_by_reference_id(row.idempotency_key)
                if remote.get("exists"):
                    verification = {
                        "executed": True,
                        "status": "confirmed",
                        "order_id": row.order_id,
                        "attempt_number": row.attempt_number,
                        "details": remote,
                    }
                else:
                    verification = {
                        "executed": False,
                        "status": "failed",
                        "order_id": row.order_id,
                        "attempt_number": row.attempt_number,
                        "details": remote,
                    }

            is_executed = verification.get("executed", False)
            remote_status = verification.get("status", "failed")

            if is_executed:
                row.status = remote_status
            else:
                row.status = "failed"

            row.evidence_json = {
                **(row.evidence_json or {}),
                "reconciled_at_startup": True,
                "reconciliation_result": verification,
            }
            session.commit()
            reconciled_events.append(row.to_dict())

        return reconciled_events
    finally:
        session.close()
