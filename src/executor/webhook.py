import os
import hmac
import hashlib
import json
import logging
from typing import Dict, Any, Tuple, Optional

logger = logging.getLogger("webhook_handler")
logger.setLevel(logging.INFO)


def verify_webhook_signature(raw_body: str, signature: str, secret: Optional[str] = None) -> bool:
    """
    Verifies Razorpay's HMAC SHA-256 webhook signature.
    Do NOT skip signature verification!
    """
    webhook_secret = secret or os.getenv("RAZORPAY_WEBHOOK_SECRET", "placeholder_webhook_secret")
    if not signature or not webhook_secret:
        return False

    computed_sig = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(computed_sig, signature)
    if not is_valid:
        logger.warning("[WEBHOOK SIGNATURE] Signature verification failed!")
    else:
        logger.info("[WEBHOOK SIGNATURE] HMAC SHA-256 Signature verified successfully.")
    return is_valid


def normalize_webhook_event(webhook_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalizes Razorpay payment.failed, subscription.charged.failed, and payout.failed events
    into the standard internal event payload expected by Classifier & Ledger.
    """
    event_type = webhook_payload.get("event", "payment.failed")
    contains = webhook_payload.get("payload", {})

    entity = {}
    if "payment" in contains:
        entity = contains["payment"].get("entity", {})
    elif "subscription" in contains:
        entity = contains["subscription"].get("entity", {})
    elif "payout" in contains:
        entity = contains["payout"].get("entity", {})
    else:
        entity = contains.get("entity", {})

    order_id = entity.get("order_id") or entity.get("id") or "ord_unknown"
    attempt_number = entity.get("attempts", 1) or 1
    error_code = (
        entity.get("error_code")
        or entity.get("error", {}).get("code")
        or "payment_failed"
    )
    error_description = (
        entity.get("error_description")
        or entity.get("error", {}).get("description")
        or ""
    )
    amount = entity.get("amount", 0)

    # Customer details
    email = entity.get("email") or entity.get("customer", {}).get("email") or "customer@example.com"
    contact = entity.get("contact") or entity.get("customer", {}).get("contact") or "+919999999999"

    normalized_event = {
        "event_type": event_type,
        "order_id": order_id,
        "attempt_number": attempt_number,
        "error_code": error_code,
        "error_description": error_description,
        "amount": amount,
        "customer": {
            "email": email,
            "contact": contact,
        },
        "raw_event_id": webhook_payload.get("event_id"),
        "created_at": webhook_payload.get("created_at"),
    }

    logger.info(
        f"[WEBHOOK NORMALIZER] Normalized {event_type} event: order_id={order_id}, attempt={attempt_number}, error={error_code}"
    )
    return normalized_event
