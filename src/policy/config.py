from dataclasses import dataclass


@dataclass
class PolicyThresholdConfig:
    """
    Centralized policy threshold configuration object.
    Holds all threshold parameters, cooldown windows, and safety limits.
    """
    max_retries: int = 3
    escalation_amount: int = 5000000  # Amount in paise (e.g. ₹50,000.00 = 5,000,000 paise)
    min_confidence: float = 0.70
    insufficient_funds_cooldown_hours: float = 24.0
    bank_transient_base_backoff_seconds: int = 300  # 5 minutes base exponential backoff
    max_elapsed_time_seconds: int = 604800  # 7 days before write-off
