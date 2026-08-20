from typing import Dict, Any
from src.policy.models import Action, ActionType


def run_static_rules_baseline(event: Dict[str, Any]) -> Action:
    """
    Baseline #2: Static Rules
    Fixed retry schedule (retries up to 3 times with fixed 300s delay) without confidence scoring,
    LLM reasoning, or risk-category adaptation.
    """
    attempt_number = event.get("attempt_number", 1)
    if attempt_number > 3:
        return Action(
            type=ActionType.ESCALATE_HUMAN,
            reason="Static Rules Baseline: attempt count > 3 reached, escalating to human",
        )

    return Action(
        type=ActionType.RETRY_SCHEDULED,
        delay_seconds=300,
        reason=f"Static Rules Baseline: fixed scheduled retry for attempt #{attempt_number}",
    )
