import logging
from typing import Dict, Any
from src.executor.razorpay_client import create_payment_link
from src.policy.models import ActionType

logger = logging.getLogger("action_executor")
logger.setLevel(logging.INFO)


def execute_policy_action(action: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the policy action determined by the Policy Engine.

    - RETRY_NOW / RETRY_SCHEDULED -> Creates a real Razorpay Payment Link via the Payment Links API,
      tagged with the idempotency_key from the ledger.
    - NUDGE_CUSTOMER / ESCALATE_HUMAN / WRITE_OFF -> Log-only actions for this submission.
      NOTE: DELIBERATE SCOPE CUT - No real SMS/Email/Slack/Zendesk delivery integration is performed
      for non-retry actions in this phase. Actions are recorded with audit logs.
    """
    order_id = action["order_id"]
    attempt_number = action["attempt_number"]
    action_type_str = action.get("action_type", "RETRY_NOW")
    idempotency_key = action.get("idempotency_key") or f"idemp_{order_id}_{attempt_number}"
    amount = action.get("amount", 100000)
    customer_info = action.get("customer", {})

    logger.info(
        f"[ACTION EXECUTOR] Dispatching action '{action_type_str}' for order_id={order_id}, attempt={attempt_number}"
    )

    if action_type_str in (ActionType.RETRY_NOW.value, ActionType.RETRY_SCHEDULED.value):
        # Create Razorpay Payment Link tagged with idempotency_key
        plink_result = create_payment_link(
            amount=amount,
            idempotency_key=idempotency_key,
            description=f"Automated Recovery Link for Order {order_id} (Attempt #{attempt_number})",
            customer_info=customer_info,
            order_id=order_id,
            attempt_number=attempt_number,
        )
        return {
            "success": plink_result.get("success", True),
            "action_type": action_type_str,
            "order_id": order_id,
            "attempt_number": attempt_number,
            "payment_link_id": plink_result.get("id"),
            "short_url": plink_result.get("short_url"),
            "details": plink_result,
        }

    elif action_type_str == ActionType.NUDGE_CUSTOMER.value:
        # DELIBERATE SCOPE CUT: Log-only action. Customer SMS/WhatsApp nudge simulated.
        logger.info(
            f"[ACTION EXECUTOR - SCOPE CUT] Action=NUDGE_CUSTOMER for order {order_id}. Audit logged, no external SMS sent."
        )
        return {
            "success": True,
            "action_type": action_type_str,
            "order_id": order_id,
            "attempt_number": attempt_number,
            "scope_cut": True,
            "message": f"Logged customer nudge request for order {order_id}",
        }

    elif action_type_str == ActionType.ESCALATE_HUMAN.value:
        # DELIBERATE SCOPE CUT: Log-only action. Human escalation ticket creation simulated.
        logger.info(
            f"[ACTION EXECUTOR - SCOPE CUT] Action=ESCALATE_HUMAN for order {order_id}. Audit logged, no Zendesk ticket opened."
        )
        return {
            "success": True,
            "action_type": action_type_str,
            "order_id": order_id,
            "attempt_number": attempt_number,
            "scope_cut": True,
            "message": f"Logged human escalation request for order {order_id}",
        }

    elif action_type_str == ActionType.WRITE_OFF.value:
        # DELIBERATE SCOPE CUT: Log-only action. Accounting write-off record simulated.
        logger.info(
            f"[ACTION EXECUTOR - SCOPE CUT] Action=WRITE_OFF for order {order_id}. Audit logged."
        )
        return {
            "success": True,
            "action_type": action_type_str,
            "order_id": order_id,
            "attempt_number": attempt_number,
            "scope_cut": True,
            "message": f"Logged transaction write-off for order {order_id}",
        }

    else:
        logger.warning(f"[ACTION EXECUTOR] Unrecognized action_type '{action_type_str}', default logging.")
        return {
            "success": True,
            "action_type": action_type_str,
            "order_id": order_id,
            "attempt_number": attempt_number,
            "message": f"Executed unknown action {action_type_str}",
        }
