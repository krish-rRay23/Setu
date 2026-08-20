from typing import Dict, Any, Optional
from src.classifier.rules import rules_classifier
from src.classifier.models import RootCauseCategory, ClassificationResult
from src.policy.engine import decide_action
from src.policy.config import PolicyThresholdConfig
from src.policy.models import Action


def run_remove_llm_ablation(
    event: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    threshold_config: Optional[PolicyThresholdConfig] = None,
) -> Action:
    """
    Ablation #1: Remove LLM Classifier
    Uses rules_classifier ONLY. Any event that is not an unambiguous error code returns None,
    forcing an abstain classification (UNKNOWN, confidence=0.0, abstain=True).
    Proves LLM's contribution to recovering ambiguous residual cases.
    """
    rule_res = rules_classifier(event)
    if rule_res is None:
        cls_result = ClassificationResult(
            category=RootCauseCategory.UNKNOWN,
            confidence=0.0,
            evidence=["Rules-only ablation: No unambiguous rule matched; LLM disabled"],
            abstain=True,
            source="rules_only_ablation",
        )
    else:
        cls_result = rule_res

    attempt_number = event.get("attempt_number", 1)
    amount = event.get("amount", 100000)
    elapsed_time = context.get("elapsed_time_seconds", 0) if context else 0

    return decide_action(
        classification=cls_result,
        attempt_count=attempt_number - 1,
        elapsed_time_since_first_attempt=elapsed_time,
        amount=amount,
        threshold_config=threshold_config,
    )
