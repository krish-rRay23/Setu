from datetime import datetime, timezone
from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    JSON,
    UniqueConstraint,
    func,
)
from src.ledger.db import Base


class LedgerEvent(Base):
    __tablename__ = "ledger_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    idempotency_key = Column(String(64), unique=True, nullable=False, index=True)
    order_id = Column(String(100), nullable=False, index=True)
    attempt_number = Column(Integer, nullable=False)
    action_type = Column(String(50), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    evidence_json = Column(JSON, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
    )

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_ledger_idempotency_key"),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "idempotency_key": self.idempotency_key,
            "order_id": self.order_id,
            "attempt_number": self.attempt_number,
            "action_type": self.action_type,
            "status": self.status,
            "evidence_json": self.evidence_json,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
