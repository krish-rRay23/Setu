from typing import Optional, Dict, Any
from src.classifier.models import RootCauseCategory, ClassificationResult

# Exact, unambiguous Razorpay error codes lookup map
UNAMBIGUOUS_ERROR_RULES: Dict[str, RootCauseCategory] = {
    # Session / Card Expiry
    "BAD_REQUEST_PAYMENT_CARD_EXPIRED": RootCauseCategory.SESSION_EXPIRED,
    "card_expired": RootCauseCategory.SESSION_EXPIRED,
    
    # Customer Abandonment / OTP Timeout
    "BAD_REQUEST_PAYMENT_OTP_EXPIRED": RootCauseCategory.CUSTOMER_ABANDONMENT,
    "BAD_REQUEST_PAYMENT_OTP_TIMEOUT": RootCauseCategory.CUSTOMER_ABANDONMENT,
    "otp_timeout": RootCauseCategory.CUSTOMER_ABANDONMENT,
    "otp_expired": RootCauseCategory.CUSTOMER_ABANDONMENT,

    # Insufficient Funds
    "BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS": RootCauseCategory.INSUFFICIENT_FUNDS,
    "insufficient_funds": RootCauseCategory.INSUFFICIENT_FUNDS,

    # Risk / Fraud Block
    "BAD_REQUEST_PAYMENT_RISK_CHECK_FAILED": RootCauseCategory.RISK_BLOCK,
    "BAD_REQUEST_PAYMENT_FRAUD_SUSPECTED": RootCauseCategory.RISK_BLOCK,
    "risk_block": RootCauseCategory.RISK_BLOCK,

    # Bank Transient Issues
    "GATEWAY_ERROR_BANK_TIMED_OUT": RootCauseCategory.BANK_TRANSIENT,
    "BAD_REQUEST_PAYMENT_DECLINED_BY_BANK": RootCauseCategory.BANK_TRANSIENT,
    "bank_timeout": RootCauseCategory.BANK_TRANSIENT,
}

# Generic / Ambiguous error codes that MUST return None and escalate to LLM
AMBIGUOUS_ERROR_CODES = {
    "payment_failed",
    "BAD_REQUEST_ERROR",
    "GATEWAY_ERROR",
    "unknown_error",
    "CUSTOMER_CANCELLED",
}


def rules_classifier(event: Dict[str, Any]) -> Optional[ClassificationResult]:
    """
    Pure lookup table mapping known, unambiguous Razorpay error codes to root-cause categories.
    Returns ClassificationResult with confidence 1.0 for unambiguous cases.
    Returns None if error code is generic or ambiguous.
    """
    error_code = event.get("error_code") or event.get("code")
    if not error_code or error_code in AMBIGUOUS_ERROR_CODES:
        return None

    category = UNAMBIGUOUS_ERROR_RULES.get(error_code)
    if category is None:
        return None

    return ClassificationResult(
        category=category,
        confidence=1.0,
        evidence=[f"Unambiguous error code matched: '{error_code}'"],
        abstain=False,
        source="rules",
    )
