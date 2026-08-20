import os
import time
import json
import logging
import requests
from typing import Dict, Any, Optional, Callable
from src.classifier.models import RootCauseCategory, ClassificationResult

logger = logging.getLogger("classifier_llm")
logger.setLevel(logging.INFO)


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


def _prune_context(event: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Prunes raw event and context down to structured signals:
    - error_code
    - timing_pattern
    - repeat_attempt_count
    - amount
    - bank
    - recent_bank_failure_rate
    """
    ctx = context or {}
    return {
        "error_code": event.get("error_code") or event.get("code", "payment_failed"),
        "error_description": event.get("error_description") or event.get("description", ""),
        "timing_pattern": ctx.get("timing_pattern", "normal"),
        "repeat_attempt_count": ctx.get("repeat_attempt_count", 1),
        "amount": event.get("amount") or ctx.get("amount", 0),
        "bank": event.get("bank") or ctx.get("bank", "UNKNOWN_BANK"),
        "recent_bank_failure_rate": ctx.get("recent_bank_failure_rate", 0.0),
    }


def gemini_live_llm_inference(pruned_evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Live Gemini API structured reasoning call using Gemini 3.6 Flash / Gemini Flash REST API.
    Enforces strict output schema: {category, confidence (0-1), evidence: [short strings], abstain: bool}.
    """
    _load_env_file_if_present()
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key or "placeholder" in api_key:
        logger.info("[LLM CLASSIFIER] No live GEMINI_API_KEY set; falling back to mock rule heuristic.")
        return default_mock_llm_inference(pruned_evidence)

    system_prompt = """You are a specialized payment diagnostics AI classifier for Razorpay transactions.
Diagnose the failure root cause from the structured signals provided.

You MUST choose category from exactly ONE of these options:
- BANK_TRANSIENT (bank server outage, gateway timeout, high bank failure rate)
- INSUFFICIENT_FUNDS (customer balance empty)
- RISK_BLOCK (suspected fraud, rapid repeat attempt velocity burst)
- CUSTOMER_ABANDONMENT (user left checkout or OTP expired)
- SESSION_EXPIRED (card expired or session timeout)
- UNKNOWN (sparse evidence, generic code, indeterminate)

Return strictly a JSON object with this exact schema:
{
  "category": "BANK_TRANSIENT|INSUFFICIENT_FUNDS|RISK_BLOCK|CUSTOMER_ABANDONMENT|SESSION_EXPIRED|UNKNOWN",
  "confidence": float_between_0_and_1,
  "evidence": ["short string 1", "short string 2"],
  "abstain": true_or_false
}

If context is sparse, ambiguous, or confidence is under 0.60, set abstain=true and category="UNKNOWN". Do not output markdown block delimiters, return plain raw JSON only."""

    prompt_body = f"Input Signals:\n{json.dumps(pruned_evidence, indent=2)}"

    # Model names confirmed by the Gemini API.
    # Primary: gemini-3.6-flash (latest, as per API 404 guidance)
    # Fallback: gemini-2.5-flash (stable, widely available)
    models_to_try = ["gemini-3.6-flash", "gemini-2.5-flash"]

    last_error = None
    for model_name in models_to_try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
        payload = {
            "contents": [{"parts": [{"text": system_prompt + "\n\n" + prompt_body}]}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }
        for attempt in range(5):
            try:
                logger.info(f"[LLM CLASSIFIER] Querying live model '{model_name}' (attempt {attempt+1})...")
                response = requests.post(url, json=payload, headers={"Content-Type": "application/json"}, timeout=30)
                if response.status_code == 200:
                    res_data = response.json()
                    text_content = res_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                    if text_content.startswith("```"):
                        text_content = text_content.strip("`").replace("json\n", "").replace("json", "").strip()
                    parsed = json.loads(text_content)
                    logger.info(f"[LLM CLASSIFIER] Live Gemini '{model_name}' OK: category={parsed.get('category')}, confidence={parsed.get('confidence')}")
                    return parsed
                elif response.status_code in (429, 503):
                    backoff = 2 ** attempt
                    logger.warning(f"[LLM CLASSIFIER] Model '{model_name}' HTTP {response.status_code}. Sleeping {backoff}s before retry...")
                    time.sleep(backoff)
                    last_error = f"HTTP {response.status_code}"
                else:
                    logger.warning(f"[LLM CLASSIFIER] Model '{model_name}' HTTP {response.status_code}: {response.text[:200]}")
                    last_error = f"HTTP {response.status_code}"
                    break  # Non-retriable error; try next model
            except Exception as e:
                logger.error(f"[LLM CLASSIFIER EXCEPTION] Model '{model_name}' attempt {attempt+1} failed: {e}")
                last_error = str(e)
                backoff = 2 ** attempt
                time.sleep(backoff)
        logger.warning(f"[LLM CLASSIFIER] All retries exhausted for model '{model_name}'. Trying next model...")

    raise RuntimeError(
        f"[LLM CLASSIFIER] All Gemini models exhausted after retries (last error: {last_error}). "
        "Evaluation cannot continue without live LLM inference."
    )


def default_mock_llm_inference(pruned_evidence: Dict[str, Any]) -> Dict[str, Any]:
    """
    Mock LLM inference engine fallback simulating structured JSON output schema.
    """
    error_code = pruned_evidence.get("error_code", "")
    repeat_attempt_count = pruned_evidence.get("repeat_attempt_count", 1)
    recent_bank_failure_rate = pruned_evidence.get("recent_bank_failure_rate", 0.0)

    if recent_bank_failure_rate > 0.4:
        return {
            "category": "BANK_TRANSIENT",
            "confidence": 0.88,
            "evidence": [
                f"High recent bank failure rate ({recent_bank_failure_rate * 100:.0f}%) observed across gateway",
                f"Generic error '{error_code}' correlated with bank downtime window",
            ],
            "abstain": False,
        }

    if repeat_attempt_count >= 3:
        return {
            "category": "RISK_BLOCK",
            "confidence": 0.82,
            "evidence": [
                f"Customer made {repeat_attempt_count} rapid attempts within short window",
                "High attempt velocity indicates potential automated script or risk flag",
            ],
            "abstain": False,
        }

    return {
        "category": "UNKNOWN",
        "confidence": 0.35,
        "evidence": [
            f"Generic error code '{error_code}' lacks specific root-cause indicators",
            "No correlation found in timing pattern or repeat history",
        ],
        "abstain": True,
    }


def llm_classifier(
    event: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    llm_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> ClassificationResult:
    """
    Invoked ONLY when rules_classifier returns None.
    Takes pruned structured evidence and queries LLM using strict JSON schema:
    {category, confidence (0-1), evidence: [short strings], abstain: bool}
    """
    pruned_evidence = _prune_context(event, context)

    if llm_fn is None:
        llm_fn = gemini_live_llm_inference

    raw_response = llm_fn(pruned_evidence)

    category_str = raw_response.get("category", "UNKNOWN")
    try:
        category = RootCauseCategory(category_str)
    except ValueError:
        category = RootCauseCategory.UNKNOWN

    confidence = float(raw_response.get("confidence", 0.0))
    evidence = raw_response.get("evidence", [])
    abstain = bool(raw_response.get("abstain", False))

    if abstain or confidence < 0.5:
        category = RootCauseCategory.UNKNOWN
        abstain = True

    return ClassificationResult(
        category=category,
        confidence=confidence,
        evidence=evidence,
        abstain=abstain,
        source="llm",
    )
