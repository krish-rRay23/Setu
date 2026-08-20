import sys
import os

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.classifier.models import ClassificationResult, RootCauseCategory
from src.policy.config import PolicyThresholdConfig
from src.policy.models import ActionType
from src.policy.engine import decide_action


def run_policy_tests():
    config = PolicyThresholdConfig(
        max_retries=3,
        escalation_amount=5000000,  # ₹50,000 in paise
        min_confidence=0.70,
        insufficient_funds_cooldown_hours=24.0,
        bank_transient_base_backoff_seconds=300,
    )

    test_matrix = [
        {
            "description": "High Value Order Threshold",
            "classification": ClassificationResult(RootCauseCategory.BANK_TRANSIENT, 1.0),
            "attempt_count": 0,
            "elapsed_time": 300,
            "amount": 6000000,  # ₹60,000
            "expected_action": ActionType.ESCALATE_HUMAN,
        },
        {
            "description": "Max Retries Cap Exceeded",
            "classification": ClassificationResult(RootCauseCategory.BANK_TRANSIENT, 1.0),
            "attempt_count": 3,  # >= max_retries
            "elapsed_time": 1800,
            "amount": 100000,
            "expected_action": ActionType.ESCALATE_HUMAN,
        },
        {
            "description": "Max Elapsed Time Cutoff",
            "classification": ClassificationResult(RootCauseCategory.BANK_TRANSIENT, 1.0),
            "attempt_count": 1,
            "elapsed_time": 700000,  # > 7 days
            "amount": 100000,
            "expected_action": ActionType.WRITE_OFF,
        },
        {
            "description": "Low Confidence / Abstain (Attempt 0)",
            "classification": ClassificationResult(RootCauseCategory.UNKNOWN, 0.40, abstain=True),
            "attempt_count": 0,
            "elapsed_time": 60,
            "amount": 100000,
            "expected_action": ActionType.NUDGE_CUSTOMER,
        },
        {
            "description": "Low Confidence / Abstain (Attempt 1)",
            "classification": ClassificationResult(RootCauseCategory.UNKNOWN, 0.40, abstain=True),
            "attempt_count": 1,
            "elapsed_time": 1200,
            "amount": 100000,
            "expected_action": ActionType.ESCALATE_HUMAN,
        },
        {
            "description": "Risk Block (Always Human Escalation)",
            "classification": ClassificationResult(RootCauseCategory.RISK_BLOCK, 1.0),
            "attempt_count": 0,
            "elapsed_time": 60,
            "amount": 100000,
            "expected_action": ActionType.ESCALATE_HUMAN,
        },
        {
            "description": "Insufficient Funds (Scheduled 24h Cooldown)",
            "classification": ClassificationResult(RootCauseCategory.INSUFFICIENT_FUNDS, 1.0),
            "attempt_count": 0,
            "elapsed_time": 60,
            "amount": 100000,
            "expected_action": ActionType.RETRY_SCHEDULED,
        },
        {
            "description": "Bank Transient Failure (Exponential Backoff Attempt 0)",
            "classification": ClassificationResult(RootCauseCategory.BANK_TRANSIENT, 1.0),
            "attempt_count": 0,
            "elapsed_time": 60,
            "amount": 100000,
            "expected_action": ActionType.RETRY_SCHEDULED,
        },
        {
            "description": "Bank Transient Failure (Exponential Backoff Attempt 1)",
            "classification": ClassificationResult(RootCauseCategory.BANK_TRANSIENT, 1.0),
            "attempt_count": 1,
            "elapsed_time": 600,
            "amount": 100000,
            "expected_action": ActionType.RETRY_SCHEDULED,
        },
        {
            "description": "Customer Abandonment (Nudge Customer)",
            "classification": ClassificationResult(RootCauseCategory.CUSTOMER_ABANDONMENT, 1.0),
            "attempt_count": 0,
            "elapsed_time": 120,
            "amount": 100000,
            "expected_action": ActionType.NUDGE_CUSTOMER,
        },
        {
            "description": "Session Expired (Nudge Customer)",
            "classification": ClassificationResult(RootCauseCategory.SESSION_EXPIRED, 1.0),
            "attempt_count": 0,
            "elapsed_time": 120,
            "amount": 100000,
            "expected_action": ActionType.NUDGE_CUSTOMER,
        },
        {
            "description": "Unknown Category (Attempt 0 -> Nudge)",
            "classification": ClassificationResult(RootCauseCategory.UNKNOWN, 0.80),
            "attempt_count": 0,
            "elapsed_time": 60,
            "amount": 100000,
            "expected_action": ActionType.NUDGE_CUSTOMER,
        },
        {
            "description": "Unknown Category (Attempt 1 -> Escalate)",
            "classification": ClassificationResult(RootCauseCategory.UNKNOWN, 0.80),
            "attempt_count": 1,
            "elapsed_time": 1200,
            "amount": 100000,
            "expected_action": ActionType.ESCALATE_HUMAN,
        },
    ]

    print("=" * 110)
    print("                           SETU POLICY ENGINE TEST MATRIX                           ")
    print("=" * 110)
    print(f"{'#':<3} | {'Rule Scenario':<42} | {'Category':<20} | {'Action Chosen':<16} | {'Delay':<8} | {'Pass/Fail'}")
    print("-" * 110)

    all_passed = True
    for idx, tc in enumerate(test_matrix, 1):
        action = decide_action(
            classification=tc["classification"],
            attempt_count=tc["attempt_count"],
            elapsed_time_since_first_attempt=tc["elapsed_time"],
            amount=tc["amount"],
            threshold_config=config,
        )

        passed = action.type == tc["expected_action"]
        if not passed:
            all_passed = False

        status_str = "PASS" if passed else "FAIL"
        delay_str = f"{action.delay_seconds}s" if action.delay_seconds else "N/A"
        cat_str = str(tc["classification"].category.value)

        print(
            f"{idx:<3} | {tc['description']:<42} | {cat_str:<20} | {action.type.value:<16} | {delay_str:<8} | [{status_str}]"
        )
        print(f"    -> Reason: {action.reason}")

    print("=" * 110)
    if all_passed:
        print("OVERALL POLICY RESULT: ALL BRANCHES PASSED PERFECTLY!")
    else:
        print("OVERALL POLICY RESULT: ONE OR MORE TEST BRANCHES FAILED!")
    print("=" * 110)


if __name__ == "__main__":
    run_policy_tests()
