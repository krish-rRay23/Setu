import os
from typing import Dict, List, Any

REQUIRED_VARS = ["RAZORPAY_KEY_ID", "RAZORPAY_KEY_SECRET"]

def validate_environment() -> Dict[str, Any]:
    missing: List[str] = [var for var in REQUIRED_VARS if not os.getenv(var)]
    return {
        "valid": len(missing) == 0,
        "missing": missing,
        "is_test_mode": os.getenv("RAZORPAY_KEY_ID", "").startswith("rzp_test_")
    }
