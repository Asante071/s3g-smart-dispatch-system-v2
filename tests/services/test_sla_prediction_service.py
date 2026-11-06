from pathlib import Path

import joblib

from services.sla_prediction_service import SLAPredictionService


SAMPLE_INCIDENT = {
    "priority": "HIGH",
    "category": "Network",
    "complexity": 8,
    "engineer_experience": 2,
    "engineer_workload": 12,
    "previous_incidents": 4,
    "sla_allowed_hours": 8,
    "incident_age_hours": 6,
    "sla_remaining_hours": 2,
}


class FixedProbabilityModel:
    classes_ = [0, 1]

    def __init__(self, breach_probability: float):
        self.breach_probability = breach_probability

    def predict_proba(self, features):
        return [[1 - self.breach_probability, self.breach_probability]]


def test_prediction_uses_all_expected_features_in_training_order():
    service = SLAPredictionService()

    result = service.predict(SAMPLE_INCIDENT)

    assert service.FEATURES == list(service.model.feature_names_in_)
    assert 0 <= result["breach_probability"] <= 1
    assert result["model_performance_note"].startswith("Model performance is based on synthetic")


def test_probability_at_threshold_is_not_high_risk(tmp_path: Path):
    artifact = tmp_path / "boundary-model.joblib"
    joblib.dump(FixedProbabilityModel(0.70), artifact)
    service = SLAPredictionService(model_path=artifact)

    result = service.predict(SAMPLE_INCIDENT)

    assert result["risk_level"] == "LOW RISK"
    assert result["high_risk_threshold"] == 0.70


def test_probability_above_threshold_is_high_risk(tmp_path: Path):
    artifact = tmp_path / "high-risk-model.joblib"
    joblib.dump(FixedProbabilityModel(0.7001), artifact)
    service = SLAPredictionService(model_path=artifact)

    assert service.predict(SAMPLE_INCIDENT)["risk_level"] == "HIGH RISK"
