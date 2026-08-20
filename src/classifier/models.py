from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class RootCauseCategory(str, Enum):
    BANK_TRANSIENT = "BANK_TRANSIENT"
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    RISK_BLOCK = "RISK_BLOCK"
    CUSTOMER_ABANDONMENT = "CUSTOMER_ABANDONMENT"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    UNKNOWN = "UNKNOWN"


@dataclass
class ClassificationResult:
    category: RootCauseCategory
    confidence: float
    evidence: List[str] = field(default_factory=list)
    abstain: bool = False
    source: str = "rules"  # "rules" or "llm"

    def to_dict(self):
        return {
            "category": self.category.value if isinstance(self.category, RootCauseCategory) else str(self.category),
            "confidence": round(self.confidence, 2),
            "evidence": self.evidence,
            "abstain": self.abstain,
            "source": self.source,
        }
