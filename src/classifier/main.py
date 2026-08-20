from typing import Dict, Any, Optional, Callable
from src.classifier.models import ClassificationResult
from src.classifier.rules import rules_classifier
from src.classifier.llm import llm_classifier


def classify_event(
    event: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None,
    llm_fn: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
) -> ClassificationResult:
    """
    Main Classifier entry point:
    1. Runs rules_classifier(event) first.
    2. If rules match, returns rules ClassificationResult immediately.
    3. If rules return None, escalates to llm_classifier(event, context).
    """
    rule_result = rules_classifier(event)
    if rule_result is not None:
        return rule_result

    return llm_classifier(event, context, llm_fn=llm_fn)
