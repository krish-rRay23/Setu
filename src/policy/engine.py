from src.classifier.models import ClassificationResult, RootCauseCategory
from src.policy.config import PolicyThresholdConfig
from src.policy.models import Action, ActionType


def decide_action(
    classification: ClassificationResult,
    attempt_count: int,
    elapsed_time_since_first_attempt: int,
    amount: int,
    threshold_config: PolicyThresholdConfig = None,
) -> Action:
    """
    Pure deterministic policy function.
    Maps (classification, attempt_count, elapsed_time, amount, threshold_config) -> Action.
    NO LLM calls, NO external API calls.
    """
    if threshold_config is None:
        threshold_config = PolicyThresholdConfig()

    category = classification.category
    confidence = classification.confidence
    abstain = classification.abstain

    # Rule 1: High Value Amount Threshold
    if amount >= threshold_config.escalation_amount:
        return Action(
            type=ActionType.ESCALATE_HUMAN,
            reason=f"Transaction amount ({amount}) exceeds high-value escalation threshold ({threshold_config.escalation_amount})",
        )

    # Rule 2: Maximum Attempt Limit Reached
    if attempt_count >= threshold_config.max_retries:
        return Action(
            type=ActionType.ESCALATE_HUMAN,
            reason=f"Attempt count ({attempt_count}) reached maximum allowed retries limit ({threshold_config.max_retries})",
        )

    # Rule 3: Max Elapsed Window Exceeded -> Write Off
    if elapsed_time_since_first_attempt >= threshold_config.max_elapsed_time_seconds:
        return Action(
            type=ActionType.WRITE_OFF,
            reason=f"Elapsed time ({elapsed_time_since_first_attempt}s) exceeded max recovery window ({threshold_config.max_elapsed_time_seconds}s)",
        )

    # Rule 4: Low Confidence / Abstention Handling (Safest Action)
    if abstain or confidence < threshold_config.min_confidence:
        if category == RootCauseCategory.RISK_BLOCK or attempt_count > 0:
            return Action(
                type=ActionType.ESCALATE_HUMAN,
                reason=f"Low confidence ({confidence:.2f}) or abstain ({abstain}) with prior attempts/risk; routing to safest action (ESCALATE_HUMAN)",
            )
        else:
            return Action(
                type=ActionType.NUDGE_CUSTOMER,
                reason=f"Low confidence ({confidence:.2f}) or abstain ({abstain}) on initial attempt; routing to safest action (NUDGE_CUSTOMER)",
            )

    # Rule 5: Root-Cause Category Specific Decisions
    if category == RootCauseCategory.RISK_BLOCK:
        return Action(
            type=ActionType.ESCALATE_HUMAN,
            reason="Risk block detected; mandatory human escalation, zero auto-retry",
        )

    if category == RootCauseCategory.INSUFFICIENT_FUNDS:
        cooldown_seconds = int(threshold_config.insufficient_funds_cooldown_hours * 3600)
        return Action(
            type=ActionType.RETRY_SCHEDULED,
            delay_seconds=cooldown_seconds,
            reason=f"Insufficient funds; scheduled retry after mandatory {threshold_config.insufficient_funds_cooldown_hours}h cooldown",
        )

    if category == RootCauseCategory.BANK_TRANSIENT:
        delay = threshold_config.bank_transient_base_backoff_seconds * (2 ** attempt_count)
        return Action(
            type=ActionType.RETRY_SCHEDULED,
            delay_seconds=delay,
            reason=f"Bank transient failure; scheduled retry with exponential backoff ({delay}s)",
        )

    if category == RootCauseCategory.CUSTOMER_ABANDONMENT or category == RootCauseCategory.SESSION_EXPIRED:
        return Action(
            type=ActionType.NUDGE_CUSTOMER,
            reason="Customer action required (abandonment/session expired); sending customer nudge",
        )

    if category == RootCauseCategory.UNKNOWN:
        if attempt_count == 0:
            return Action(
                type=ActionType.NUDGE_CUSTOMER,
                reason="Unknown failure cause on initial attempt; nudging customer to re-verify payment",
            )
        else:
            return Action(
                type=ActionType.ESCALATE_HUMAN,
                reason="Unknown failure cause with prior failed attempts; escalating to human review",
            )

    # Default Fallback
    return Action(
        type=ActionType.ESCALATE_HUMAN,
        reason="Unmatched policy condition; safe fallback to human escalation",
    )
