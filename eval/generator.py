import random
import json
import os
from typing import List, Dict, Any, Tuple
from src.classifier.models import RootCauseCategory


def generate_synthetic_dataset(
    num_events: int = 800, seed: int = 42
) -> Tuple[List[Dict[str, Any]], List[RootCauseCategory]]:
    """
    Generates a reproducible held-out synthetic dataset containing 70% clean/unambiguous events
    and 30% deliberately ambiguous/noisy/conflicting events.

    GROUND TRUTH IS STRICTLY LATENT:
    Ground truth root cause is stored separately in the ground_truth list (and in event['_ground_truth']),
    which is NEVER passed to the classifier or policy engines during evaluation.
    """
    random.seed(seed)

    clean_count = int(num_events * 0.70)  # 560 events
    ambiguous_count = num_events - clean_count  # 240 events

    events = []
    ground_truth = []

    # Clean Error Code Mappings (70% - 560 events)
    clean_templates = [
        ("BAD_REQUEST_PAYMENT_CARD_EXPIRED", RootCauseCategory.SESSION_EXPIRED),
        ("BAD_REQUEST_PAYMENT_OTP_TIMEOUT", RootCauseCategory.CUSTOMER_ABANDONMENT),
        ("BAD_REQUEST_PAYMENT_INSUFFICIENT_FUNDS", RootCauseCategory.INSUFFICIENT_FUNDS),
        ("BAD_REQUEST_PAYMENT_RISK_CHECK_FAILED", RootCauseCategory.RISK_BLOCK),
        ("GATEWAY_ERROR_BANK_TIMED_OUT", RootCauseCategory.BANK_TRANSIENT),
    ]

    category_counts = {cat.value: 0 for cat in RootCauseCategory}
    ambiguity_counts = {"clean": 0, "high_risk_burst": 0, "bank_downtime": 0, "sparse_unknown": 0, "conflicting_signal": 0}

    for i in range(clean_count):
        template_code, true_cat = random.choice(clean_templates)
        order_id = f"ord_clean_{i+1:04d}"
        amount = random.choice([50000, 100000, 250000, 500000, 1500000])  # in paise
        event = {
            "order_id": order_id,
            "attempt_number": 1,
            "error_code": template_code,
            "error_description": f"Clean error for {template_code}",
            "amount": amount,
            "customer": {"email": f"cust_{i}@example.com", "contact": "+919876543210"},
            "context": {
                "timing_pattern": "normal",
                "repeat_attempt_count": 1,
                "recent_bank_failure_rate": 0.05,
                "elapsed_time_seconds": 60,
            },
            "_ground_truth": true_cat.value,  # Latent ground truth
        }
        events.append(event)
        ground_truth.append(true_cat)
        category_counts[true_cat.value] += 1
        ambiguity_counts["clean"] += 1

    # Ambiguous / Noisy / Conflicting Templates (30% - 240 events)
    for j in range(ambiguous_count):
        order_id = f"ord_ambig_{j+1:04d}"
        amount = random.choice([100000, 200000, 4500000, 6000000])

        ambig_type = random.choice(["high_risk_burst", "bank_downtime", "sparse_unknown", "conflicting_signal"])
        ambiguity_counts[ambig_type] += 1

        if ambig_type == "high_risk_burst":
            # Generic payment_failed with high repeat attempts -> RISK_BLOCK
            event = {
                "order_id": order_id,
                "attempt_number": random.choice([3, 4]),
                "error_code": "payment_failed",
                "error_description": "Generic failure code with high frequency attempts",
                "amount": amount,
                "customer": {"email": f"risk_user_{j}@example.com", "contact": "+919876543210"},
                "context": {
                    "timing_pattern": "rapid_burst",
                    "repeat_attempt_count": random.choice([3, 4]),
                    "recent_bank_failure_rate": 0.10,
                    "elapsed_time_seconds": 1200,
                },
                "_ground_truth": RootCauseCategory.RISK_BLOCK.value,
            }
            true_cat = RootCauseCategory.RISK_BLOCK

        elif ambig_type == "bank_downtime":
            # Generic GATEWAY_ERROR during high bank failure window -> BANK_TRANSIENT
            event = {
                "order_id": order_id,
                "attempt_number": 1,
                "error_code": "GATEWAY_ERROR",
                "error_description": "Generic gateway failure during peak bank outage",
                "amount": amount,
                "customer": {"email": f"bank_user_{j}@example.com", "contact": "+919876543210"},
                "context": {
                    "timing_pattern": "correlated_downtime",
                    "repeat_attempt_count": 1,
                    "recent_bank_failure_rate": 0.65,
                    "elapsed_time_seconds": 300,
                },
                "_ground_truth": RootCauseCategory.BANK_TRANSIENT.value,
            }
            true_cat = RootCauseCategory.BANK_TRANSIENT

        elif ambig_type == "conflicting_signal":
            # Conflicting signals: High amount + generic error code -> RISK_BLOCK
            event = {
                "order_id": order_id,
                "attempt_number": 2,
                "error_code": "BAD_REQUEST_ERROR",
                "error_description": "Generic bad request error with high value transaction",
                "amount": 6000000,  # ₹60,000 paise
                "customer": {"email": f"conflict_user_{j}@example.com", "contact": "+919876543210"},
                "context": {
                    "timing_pattern": "rapid_burst",
                    "repeat_attempt_count": 2,
                    "recent_bank_failure_rate": 0.05,
                    "elapsed_time_seconds": 450,
                },
                "_ground_truth": RootCauseCategory.RISK_BLOCK.value,
            }
            true_cat = RootCauseCategory.RISK_BLOCK

        else:
            # Sparse unknown error -> UNKNOWN (triggers abstain)
            event = {
                "order_id": order_id,
                "attempt_number": 1,
                "error_code": "payment_failed",
                "error_description": "Payment failed without detailed diagnostics",
                "amount": amount,
                "customer": {"email": f"sparse_user_{j}@example.com", "contact": "+919876543210"},
                "context": {
                    "timing_pattern": "normal",
                    "repeat_attempt_count": 1,
                    "recent_bank_failure_rate": 0.05,
                    "elapsed_time_seconds": 60,
                },
                "_ground_truth": RootCauseCategory.UNKNOWN.value,
            }
            true_cat = RootCauseCategory.UNKNOWN

        events.append(event)
        ground_truth.append(true_cat)
        category_counts[true_cat.value] += 1

    # Save dataset distribution report
    report = {
        "num_events": num_events,
        "seed": seed,
        "clean_count": clean_count,
        "ambiguous_count": ambiguous_count,
        "category_distribution": category_counts,
        "ambiguity_distribution": ambiguity_counts,
    }
    os.makedirs("eval", exist_ok=True)
    with open("eval/dataset_report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    return events, ground_truth
