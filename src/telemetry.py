import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict

class AuditLogger:
    def __init__(self, logger_name: str = "setu.audit"):
        self.logger = logging.getLogger(logger_name)

    def log_event(self, event_type: str, payload: Dict[str, Any]) -> str:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "payload": self._sanitize(payload)
        }
        json_line = json.dumps(record)
        self.logger.info(json_line)
        return json_line

    def _sanitize(self, data: Dict[str, Any]) -> Dict[str, Any]:
        sensitive_keys = {"card_number", "cvv", "secret", "token", "password"}
        sanitized = {}
        for k, v in data.items():
            if any(s in k.lower() for s in sensitive_keys):
                sanitized[k] = "[REDACTED]"
            elif isinstance(v, dict):
                sanitized[k] = self._sanitize(v)
            else:
                sanitized[k] = v
        return sanitized
