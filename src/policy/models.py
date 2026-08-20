from dataclasses import dataclass
from enum import Enum
from typing import Optional


class ActionType(str, Enum):
    RETRY_NOW = "RETRY_NOW"
    RETRY_SCHEDULED = "RETRY_SCHEDULED"
    NUDGE_CUSTOMER = "NUDGE_CUSTOMER"
    ESCALATE_HUMAN = "ESCALATE_HUMAN"
    WRITE_OFF = "WRITE_OFF"


@dataclass
class Action:
    type: ActionType
    delay_seconds: Optional[int] = None
    reason: str = ""

    def to_dict(self):
        return {
            "type": self.type.value if isinstance(self.type, ActionType) else str(self.type),
            "delay_seconds": self.delay_seconds,
            "reason": self.reason,
        }
