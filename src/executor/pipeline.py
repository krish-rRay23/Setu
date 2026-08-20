import logging
from typing import Dict, Any, Optional

from src.classifier.main import classify_event
from src.policy.engine import decide_action
from src.policy.config import PolicyThresholdConfig
from src.ledger.executor import record_and_execute, compute_idempotency_key
from src.executor.action_executor import execute_policy_action

logger = logging.getLogger("pipeline")
logger.setLevel(logging.INFO)


def run_pipeline_for_event(
    event: Dict[str, Any],
    session_factory,
    context: Optional[Dict[str, Any]] = None,
    threshold_config: Optional[PolicyThresholdConfig] = None,
    llm_fn=None,
) -> Dict[str, Any]:
    """
    Executes the full Setu Agent loop end-to-end:
    Observe (webhook event) -> Reason (Classifier) -> Decide (Policy) -> Act (Executor) -> Verify (Ledger)

    Guarantees:
    - Write-Ahead Ledger commit BEFORE external API call
    - Database unique constraint enforcement on idempotency_key
    - Zero duplicate executions
    """
    order_id = event["order_id"]
    attempt_number = event.get("attempt_number", 1)
    amount = event.get("amount", 100000)
    elapsed_time = context.get("elapsed_time_seconds", 0) if context else 0

    logger.info("=" * 60)
    logger.info(f"SETU AGENT PIPELINE: Processing order_id={order_id}, attempt={attempt_number}")
    logger.info("=" * 60)

    # 1. OBSERVE
    logger.info(f"[STEP 1: OBSERVE] Ingested event type={event.get('event_type')}, error_code={event.get('error_code')}")

    # 2. REASON (Classifier)
    classification = classify_event(event, context, llm_fn=llm_fn)
    logger.info(
        f"[STEP 2: REASON] Classification -> Category: {classification.category.value}, Confidence: {classification.confidence:.2f}, Source: {classification.source}, Abstain: {classification.abstain}"
    )

    # 3. DECIDE (Policy)
    policy_action = decide_action(
        classification=classification,
        attempt_count=attempt_number - 1,  # 0-indexed attempt count for policy retries
        elapsed_time_since_first_attempt=elapsed_time,
        amount=amount,
        threshold_config=threshold_config,
    )
    logger.info(
        f"[STEP 3: DECIDE] Policy Decision -> Action: {policy_action.type.value}, Delay: {policy_action.delay_seconds}s, Reason: {policy_action.reason}"
    )

    # 4. ACT & RECORD (Ledger Write-Ahead + Executor)
    idempotency_key = compute_idempotency_key(order_id, attempt_number)
    action_payload = {
        "order_id": order_id,
        "attempt_number": attempt_number,
        "action_type": policy_action.type.value,
        "amount": amount,
        "customer": event.get("customer", {}),
        "idempotency_key": idempotency_key,
        "evidence_json": {
            "classification": classification.to_dict(),
            "policy_action": policy_action.to_dict(),
            "event": event,
        },
    }

    logger.info(f"[STEP 4: ACT & RECORD] Invoking record_and_execute() with idempotency_key={idempotency_key[:16]}...")
    execution_result = record_and_execute(
        action=action_payload,
        session_factory=session_factory,
        executor_fn=execute_policy_action,
    )

    # 5. VERIFY
    logger.info(
        f"[STEP 5: VERIFY] Pipeline Execution Complete -> Duplicate: {execution_result['duplicate']}, Executed: {execution_result['executed']}, Status: {execution_result['status']}"
    )
    logger.info("=" * 60)

    return {
        "order_id": order_id,
        "attempt_number": attempt_number,
        "idempotency_key": idempotency_key,
        "classification": classification.to_dict(),
        "policy_action": policy_action.to_dict(),
        "execution_result": execution_result,
    }
