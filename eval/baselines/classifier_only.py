from typing import Dict, Any
from src.classifier.main import classify_event
from src.classifier.models import RootCauseCategory
from src.policy.models import Action, ActionType


def run_classifier_only_baseline(event: Dict[str, Any], context: Dict[str, Any] = None) -> Action:
    """
    Baseline #3: Classifier Only (No Policy caps, No Ledger unique safety)
    Uses Phase 2's classifier but lacks policy thresholds (high amount caps, max retry caps, safe fallbacks)
    and lacks ledger write-ahead unique constraint protection. Demonstrates double-action risk under concurrency.
    """
    cls_result = classify_event(event, context)

    # Naive mapping directly from category without policy caps
    if cls_result.category in (
        RootCauseCategory.BANK_TRANSIENT,
        RootCauseCategory.INSUFFICIENT_FUNDS,
        RootCauseCategory.UNKNOWN,
    ):
        return Action(
            type=ActionType.RETRY_NOW,
            reason=f"Classifier Only Baseline: direct RETRY_NOW on category {cls_result.category.value}",
        )
    elif cls_result.category == RootCauseCategory.RISK_BLOCK:
        return Action(
            type=ActionType.ESCALATE_HUMAN,
            reason="Classifier Only Baseline: ESCALATE_HUMAN on RISK_BLOCK",
        )
    else:
        return Action(
            type=ActionType.NUDGE_CUSTOMER,
            reason="Classifier Only Baseline: NUDGE_CUSTOMER",
        )
