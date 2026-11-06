"""Persistence and retrieval for SLA prediction audit records."""

from typing import Any

from database import SessionLocal
from repositories.database_models import PredictionAuditModel


class PredictionAuditService:
    def __init__(self, session_factory=SessionLocal) -> None:
        self.session_factory = session_factory

    def record(self, incident: dict[str, Any], prediction: dict[str, Any]) -> None:
        """Persist a prediction with its exact input values and model identity."""
        db = self.session_factory()
        try:
            db.add(
                PredictionAuditModel(
                    **incident,
                    breach_probability=prediction["breach_probability"],
                    risk_level=prediction["risk_level"],
                    high_risk_threshold=prediction["high_risk_threshold"],
                    model_version=prediction["model_version"],
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_recent(self, limit: int = 20) -> list[dict[str, Any]]:
        db = self.session_factory()
        try:
            records = (
                db.query(PredictionAuditModel)
                .order_by(PredictionAuditModel.created_at.desc(), PredictionAuditModel.id.desc())
                .limit(limit)
                .all()
            )
            return [
                {
                    "id": record.id,
                    "created_at": record.created_at.isoformat(),
                    "model_version": record.model_version,
                    "priority": record.priority,
                    "category": record.category,
                    "breach_probability": record.breach_probability,
                    "risk_level": record.risk_level,
                    "high_risk_threshold": record.high_risk_threshold,
                }
                for record in records
            ]
        finally:
            db.close()
