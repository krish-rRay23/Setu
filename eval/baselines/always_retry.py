from typing import Dict, Any
from src.policy.models import Action, ActionType


def run_always_retry_baseline(event: Dict[str, Any]) -> Action:
    """
    Baseline #1: Always Retry
    Naive baseline that unconditionally attempts RETRY_NOW for every single payment failure.
    Ignores risk blocks, attempt limits, amount thresholds, and confidence.
    """
    return Action(
        type=ActionType.RETRY_NOW,
        delay_seconds=0,
        reason="Baseline Always Retry: unconditionally attempting RETRY_NOW",
    )
