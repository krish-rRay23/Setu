import sys
import os
import json

# Add project root to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.classifier.models import RootCauseCategory, ClassificationResult
from src.classifier.rules import rules_classifier
from src.classifier.llm import llm_classifier
from src.classifier.main import classify_event


def run_classifier_demo():
    print("=" * 75)
    print("           SETU CLASSIFIER DEMONSTRATION & EXAMPLES           ")
    print("=" * 75)

    test_cases = [
        # --- 3 Rules-Only Examples ---
        {
            "name": "Example 1 (Rules-Only): Card Expired Error",
            "event": {
                "order_id": "ord_101",
                "error_code": "BAD_REQUEST_PAYMENT_CARD_EXPIRED",
                "description": "Card has expired",
            },
            "context": None,
        },
        {
            "name": "Example 2 (Rules-Only): OTP Timeout Error",
            "event": {
                "order_id": "ord_102",
                "error_code": "BAD_REQUEST_PAYMENT_OTP_TIMEOUT",
                "description": "OTP verification timed out by user",
            },
            "context": None,
        },
        {
            "name": "Example 3 (Rules-Only): Insufficient Funds",
            "event": {
                "order_id": "ord_103",
                "error_code": "BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS",
                "description": "Account balance insufficient",
            },
            "context": None,
        },
        # --- 2 LLM-Escalated Examples ---
        {
            "name": "Example 4 (LLM Escalated): Ambiguous Failure with High Velocity Pattern",
            "event": {
                "order_id": "ord_104",
                "error_code": "payment_failed",
                "description": "Payment could not be processed",
            },
            "context": {
                "repeat_attempt_count": 4,
                "timing_pattern": "rapid_retry_burst",
                "amount": 499900,
            },
        },
        {
            "name": "Example 5 (LLM Escalated - Abstention): Ambiguous Gateway Error with Sparse Context",
            "event": {
                "order_id": "ord_105",
                "error_code": "GATEWAY_ERROR",
                "description": "Gateway processing error",
            },
            "context": {
                "repeat_attempt_count": 1,
                "timing_pattern": "normal",
                "recent_bank_failure_rate": 0.05,
            },
        },
    ]

    for idx, tc in enumerate(test_cases, 1):
        print(f"\n--- {tc['name']} ---")
        event = tc["event"]
        context = tc["context"]

        # Step 1: Run rules classifier
        rule_res = rules_classifier(event)
        
        if rule_res is not None:
            final_res = rule_res
            print(f"  [Pipeline Step 1] Rules Classifier -> MATCHED!")
        else:
            print(f"  [Pipeline Step 1] Rules Classifier -> Returned None (Escalating to LLM...)")
            # Step 2: Escalated to LLM classifier
            final_res = llm_classifier(event, context)
            print(f"  [Pipeline Step 2] LLM Classifier -> Processed Pruned Evidence")

        print("  Classification Result:")
        print(f"    • Source:       {final_res.source.upper()}")
        print(f"    • Category:     {final_res.category}")
        print(f"    • Confidence:   {final_res.confidence:.2f}")
        print(f"    • Abstain:      {final_res.abstain}")
        print(f"    • Evidence:     {final_res.evidence}")

    print("\n" + "=" * 75)
    print("                     CLASSIFIER DEMO COMPLETE                     ")
    print("=" * 75)


if __name__ == "__main__":
    run_classifier_demo()
