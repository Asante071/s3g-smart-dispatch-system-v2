"""SLA breach-risk predictions backed by the trained model artifact."""

from pathlib import Path
from typing import Any
from hashlib import sha256

import joblib
import pandas as pd


class SLAPredictionService:
    """Load the trained pipeline once and expose its breach probability."""

    FEATURES = [
        "priority",
        "category",
        "complexity",
        "engineer_experience",
        "engineer_workload",
        "previous_incidents",
        "sla_allowed_hours",
        "incident_age_hours",
        "sla_remaining_hours",
    ]
    HIGH_RISK_THRESHOLD = 0.70

    def __init__(self, model_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parent.parent
        self.model_path = model_path or (
            project_root / "ml" / "artifacts" / "sla_random_forest.joblib"
        )
        self.model = joblib.load(self.model_path)
        self.model_version = f"sha256:{sha256(self.model_path.read_bytes()).hexdigest()[:12]}"

    def predict(self, incident: dict[str, Any]) -> dict[str, Any]:
        """Predict an SLA breach probability for one incident's nine inputs."""
        features = pd.DataFrame([{name: incident[name] for name in self.FEATURES}])
        probabilities = self.model.predict_proba(features)[0]
        positive_class_index = list(self.model.classes_).index(1)
        breach_probability = float(probabilities[positive_class_index])

        return {
            "breach_probability": round(breach_probability, 4),
            "risk_level": (
                "HIGH RISK"
                if breach_probability > self.HIGH_RISK_THRESHOLD
                else "LOW RISK"
            ),
            "high_risk_threshold": self.HIGH_RISK_THRESHOLD,
            "model_version": self.model_version,
            "model_performance_note": (
                "Model performance is based on synthetic IT incident data and "
                "must be validated against production data before operational use."
            ),
        }
