import sys
import os
import time
import hmac
import hashlib
import json

# Add root directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.ledger.db import init_db, get_session_factory
from src.ledger.models import LedgerEvent
from src.executor.webhook import verify_webhook_signature, normalize_webhook_event
from src.executor.pipeline import run_pipeline_for_event


def run_pipeline_demo():
    print("=" * 80)
    print("      SETU FULL END-TO-END AGENT PIPELINE & RAZORPAY TRACE DEMO      ")
    print("=" * 80)

    # 1. Setup DB
    db_path = "sqlite:///demo_pipeline.db"
    if os.path.exists("demo_pipeline.db"):
        os.remove("demo_pipeline.db")

    engine = init_db(db_url=db_path)
    session_factory = get_session_factory(engine)

    # 2. Simulate incoming Razorpay payment.failed webhook
    webhook_secret = "test_webhook_secret_123"
    os.environ["RAZORPAY_WEBHOOK_SECRET"] = webhook_secret

    raw_webhook_payload = {
        "event": "payment.failed",
        "event_id": f"evt_test_payment_failed_{int(time.time())}",
        "created_at": int(time.time()),
        "payload": {
            "payment": {
                "entity": {
                    "id": f"pay_test_failed_{int(time.time())}",
                    "order_id": f"ord_setu_live_{int(time.time())}",
                    "amount": 250000,  # ₹2,500.00
                    "currency": "INR",
                    "status": "failed",
                    "attempts": 1,
                    "error_code": "BAD_REQUEST_PAYMENT_DECLINED_BY_BANK",
                    "error_description": "Payment was declined by issuing bank due to transient connection timeout",
                    "email": "customer.setu@example.com",
                    "contact": "+919876543210",
                }
            }
        },
    }

    raw_body_str = json.dumps(raw_webhook_payload)

    # Generate HMAC SHA-256 signature
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        raw_body_str.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    print("\n--- PHASE 1: WEBHOOK INGESTION & SIGNATURE VERIFICATION ---")
    print(f"  • Incoming Event Type: payment.failed")
    print(f"  • Raw Signature:      {signature[:20]}...")
    
    is_valid = verify_webhook_signature(raw_body_str, signature, secret=webhook_secret)
    print(f"  • Signature Verification Result: {'VALID (Passed)' if is_valid else 'INVALID (Failed)'}")

    if not is_valid:
        print("Signature verification failed! Aborting pipeline.")
        return 1

    # 3. Normalize Webhook Event
    event = normalize_webhook_event(raw_webhook_payload)
    print(f"  • Normalized Event: order_id={event['order_id']}, amount={event['amount']}, error_code={event['error_code']}")

    # 4. Run Full Pipeline
    print("\n--- PHASE 2: END-TO-END PIPELINE EXECUTION ---")
    context = {"elapsed_time_seconds": 60}
    
    pipeline_result = run_pipeline_for_event(
        event=event,
        session_factory=session_factory,
        context=context,
    )

    # 5. Display Full Pipeline Trace
    print("\n--- PHASE 3: PIPELINE EXECUTION TRACE BREAKDOWN ---")
    print("1. OBSERVE:")
    print(f"   • Order ID:           {pipeline_result['order_id']}")
    print(f"   • Attempt Number:     {pipeline_result['attempt_number']}")
    print(f"   • Idempotency Key:    {pipeline_result['idempotency_key']}")

    print("\n2. REASON (Classifier):")
    cls = pipeline_result["classification"]
    print(f"   • Root Cause:        {cls['category']}")
    print(f"   • Confidence:        {cls['confidence']}")
    print(f"   • Source:            {cls['source']}")
    print(f"   • Evidence:          {cls['evidence']}")

    print("\n3. DECIDE (Policy):")
    pol = pipeline_result["policy_action"]
    print(f"   • Chosen Action:     {pol['type']}")
    print(f"   • Scheduled Delay:   {pol['delay_seconds']}s")
    print(f"   • Policy Rationale:  {pol['reason']}")

    print("\n4. ACT (Razorpay Payment Links API):")
    ex = pipeline_result["execution_result"]
    ev_details = ex.get("event", {}).get("evidence_json", {}).get("executor_result", {}).get("details", {})
    print(f"   • Duplicate Blocked: {ex['duplicate']}")
    print(f"   • Executed:          {ex['executed']}")
    print(f"   • Payment Link ID:   {ev_details.get('id', 'N/A')}")
    print(f"   • Payment Link URL:  {ev_details.get('short_url', 'N/A')}")
    print(f"   • Tagged Ref ID:     {ev_details.get('reference_id', 'N/A')}")
    print(f"   • Execution Status:  {ev_details.get('status', 'N/A')}")

    print("\n5. VERIFY (Ledger Record):")
    session = session_factory()
    db_event = session.query(LedgerEvent).filter_by(order_id=pipeline_result["order_id"]).first()
    session.close()

    if db_event:
        print(f"   • DB Record ID:      {db_event.id}")
        print(f"   • DB Status:         {db_event.status.upper()}")
        print(f"   • DB Created At:     {db_event.created_at}")

    print("\n" + "=" * 80)
    print("           END-TO-END PIPELINE TRACE COMPLETED SUCCESSFULLY           ")
    print("=" * 80)

    # Cleanup demo database
    engine.dispose()
    if os.path.exists("demo_pipeline.db"):
        os.remove("demo_pipeline.db")

    return 0


if __name__ == "__main__":
    sys.exit(run_pipeline_demo())
