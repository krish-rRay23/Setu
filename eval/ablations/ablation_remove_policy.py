from typing import Dict, Any
from src.policy.models import Action, ActionType


def run_remove_policy_ablation(event: Dict[str, Any]) -> Action:
    """
    Ablation #3: Remove Policy Rules
    Always attempts RETRY_NOW regardless of classification, confidence, risk blocks,
    high monetary value, or max retry count.
    Proves policy engine's role in risk mitigation and cost bounds.
    """
    return Action(
        type=ActionType.RETRY_NOW,
        delay_seconds=0,
        reason="Policy-removed ablation: Always retry regardless of policy rules",
    )
