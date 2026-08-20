import os
import logging
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("razorpay_client")
logger.setLevel(logging.INFO)

RAZORPAY_API_BASE = "https://api.razorpay.com/v1"


def _load_env_file_if_present():
    """Helper to auto-load .env file from workspace root if present."""
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    env_path = os.path.join(root_dir, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() not in os.environ:
                            os.environ[k.strip()] = v.strip()
        except Exception as e:
            logger.warning(f"Could not load .env file: {e}")


def get_razorpay_credentials() -> tuple[str, str]:
    """Loads Razorpay test mode Key ID and Secret from environment variables."""
    _load_env_file_if_present()
    key_id = os.getenv("RAZORPAY_KEY_ID", "rzp_test_placeholder_key_id")
    key_secret = os.getenv("RAZORPAY_KEY_SECRET", "placeholder_key_secret")
    return key_id, key_secret


def create_payment_link(
    amount: int,
    idempotency_key: str,
    description: str = "Payment Recovery Link",
    customer_info: Optional[Dict[str, str]] = None,
    order_id: Optional[str] = None,
    attempt_number: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Creates a Razorpay Payment Link via the Payment Links API (POST /v1/payment_links).
    Tags the link with the ledger's idempotency_key as reference_id.
    """
    key_id, key_secret = get_razorpay_credentials()
    url = f"{RAZORPAY_API_BASE}/payment_links"

    cust = customer_info or {}
    payload = {
        "amount": amount,
        "currency": "INR",
        "accept_partial": False,
        "reference_id": idempotency_key[:40],  # Razorpay reference_id max length constraint
        "description": description,
        "customer": {
            "name": cust.get("name", "Customer"),
            "email": cust.get("email", "customer@example.com"),
            "contact": cust.get("contact", "+919876543210"),
        },
        "notify": {"sms": False, "email": False},
        "reminder_enable": False,
        "notes": {
            "idempotency_key": idempotency_key,
            "order_id": order_id or "",
            "attempt_number": str(attempt_number or 1),
            "source": "Setu-Ledger-Executor",
        },
    }

    # If placeholders are detected in environment, perform a clean test-mode mock fallback response
    if "placeholder" in key_id or "placeholder" in key_secret:
        logger.info(
            f"[RAZORPAY TEST CLIENT] (Placeholder Keys Detected) Simulating API POST /v1/payment_links for reference_id={idempotency_key}"
        )
        fake_plink_id = f"plink_test_{idempotency_key[:12]}"
        return {
            "success": True,
            "id": fake_plink_id,
            "short_url": f"https://rzp.io/i/{fake_plink_id}",
            "status": "created",
            "amount": amount,
            "currency": "INR",
            "reference_id": idempotency_key,
            "mock_mode": True,
            "message": "Payment link created successfully (Test-Mode Mock)",
        }

    try:
        logger.info(
            f"[RAZORPAY TEST CLIENT] Live POST /v1/payment_links with reference_id={idempotency_key[:40]}"
        )
        response = requests.post(
            url,
            json=payload,
            auth=(key_id, key_secret),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )

        if response.status_code in (200, 201):
            data = response.json()
            logger.info(
                f"[RAZORPAY TEST CLIENT] LIVE Payment Link Created: ID={data.get('id')}, short_url={data.get('short_url')}"
            )
            return {
                "success": True,
                "id": data.get("id"),
                "short_url": data.get("short_url"),
                "status": data.get("status"),
                "amount": data.get("amount"),
                "currency": data.get("currency"),
                "reference_id": data.get("reference_id"),
                "mock_mode": False,
                "raw_response": data,
            }
        else:
            logger.error(
                f"[RAZORPAY TEST CLIENT ERROR] Status {response.status_code}: {response.text}"
            )
            return {
                "success": False,
                "status_code": response.status_code,
                "error": response.text,
                "reference_id": idempotency_key,
            }
    except Exception as e:
        logger.error(f"[RAZORPAY TEST CLIENT EXCEPTION] Failed to connect: {e}")
        return {
            "success": False,
            "error": str(e),
            "reference_id": idempotency_key,
        }


def fetch_payment_link_by_reference_id(idempotency_key: str) -> Dict[str, Any]:
    """
    Queries Razorpay's GET /v1/payment_links API filtering by reference_id.
    Used during crash recovery reconciliation to inspect actual remote Razorpay state.
    """
    key_id, key_secret = get_razorpay_credentials()
    if "placeholder" in key_id or "placeholder" in key_secret:
        return {"exists": False, "status": "unknown", "mock_mode": True}

    ref_id = idempotency_key[:40]
    url = f"{RAZORPAY_API_BASE}/payment_links"

    try:
        logger.info(f"[RAZORPAY TEST CLIENT] GET /v1/payment_links?reference_id={ref_id}")
        response = requests.get(
            url,
            auth=(key_id, key_secret),
            params={"reference_id": ref_id},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            links = data.get("payment_links", [])
            if links:
                first_link = links[0]
                logger.info(f"[RAZORPAY TEST CLIENT] Found remote Payment Link ID={first_link.get('id')}, status={first_link.get('status')}")
                return {
                    "exists": True,
                    "id": first_link.get("id"),
                    "short_url": first_link.get("short_url"),
                    "status": first_link.get("status"),
                    "amount": first_link.get("amount"),
                    "raw_response": first_link,
                }
            else:
                logger.info(f"[RAZORPAY TEST CLIENT] No remote Payment Link found for reference_id={ref_id}")
                return {"exists": False, "status": "not_found"}
        else:
            logger.error(f"[RAZORPAY TEST CLIENT ERROR] Status {response.status_code}: {response.text}")
            return {"exists": False, "error": response.text}
    except Exception as e:
        logger.error(f"[RAZORPAY TEST CLIENT EXCEPTION] Failed to query: {e}")
        return {"exists": False, "error": str(e)}

