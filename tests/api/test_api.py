import importlib

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from repositories.database_engineer_repository import DatabaseEngineerRepository
from repositories.inmemory.inmemory_ticket_repository import InMemoryTicketRepository
from services.engineer_management_service import EngineerManagementService
from services.ticket_service import TicketService

app_module = importlib.import_module("api.app")
app = app_module.app

client = TestClient(app)


def auth_headers(email):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "DispatchDemo!2026"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def supervisor_headers():
    return auth_headers("supervisor@s3g.local")


def technician_headers():
    return auth_headers("sarah@s3g.local")


def employee_headers():
    return auth_headers("employee@s3g.local")


def test_get_tickets():
    response = client.get("/api/tickets", headers=supervisor_headers())
    assert response.status_code == 200


def test_get_ticket():
    response = client.get("/api/tickets/1", headers=supervisor_headers())
    assert response.status_code == 200


def test_frontend_is_served_from_the_same_origin_as_the_api():
    response = client.get("/")

    assert response.status_code == 200
    assert "Company sign in" in response.text
    assert 'src="role-app.js"' in response.text


def test_create_ticket(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "ticket_service",
        TicketService(InMemoryTicketRepository(), seed_demo_data=False),
    )
    response = client.post(
        "/api/tickets",
        json={
            "title": "Network issue",
            "priority": "HIGH"
        },
        headers=employee_headers(),
    )
    assert response.status_code == 200
    assert response.json()["reporter_email"] == "employee@s3g.local"


def test_predict_sla_breach():
    response = client.post(
        "/api/predict",
        json={
            "priority": "HIGH",
            "category": "Network",
            "complexity": 8,
            "engineer_experience": 2,
            "engineer_workload": 12,
            "previous_incidents": 4,
            "sla_allowed_hours": 8,
            "incident_age_hours": 6,
            "sla_remaining_hours": 2,
        },
        headers=supervisor_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert set(body) == {
        "breach_probability",
        "risk_level",
        "high_risk_threshold",
        "model_version",
        "model_performance_note",
    }
    assert 0 <= body["breach_probability"] <= 1
    assert body["high_risk_threshold"] == 0.70
    assert body["model_version"].startswith("sha256:")


def test_predict_requires_all_nine_features():
    response = client.post(
        "/api/predict",
        json={
            "priority": "HIGH",
            "category": "Network",
            "complexity": 8,
            "engineer_experience": 2,
            "engineer_workload": 12,
            "previous_incidents": 4,
            "sla_allowed_hours": 8,
            "incident_age_hours": 6,
        },
        headers=technician_headers(),
    )

    assert response.status_code == 422


def test_prediction_is_added_to_audit_history():
    response = client.get("/api/predictions?limit=1", headers=supervisor_headers())

    assert response.status_code == 200
    history = response.json()
    assert len(history) == 1
    assert history[0]["model_version"].startswith("sha256:")
    assert history[0]["risk_level"] in {"HIGH RISK", "LOW RISK"}


def test_dispatch_recommendations_are_ranked_and_explain_limitations():
    response = client.post(
        "/api/dispatch/recommendations",
        json={
            "engineers": [
                {"id": 1, "name": "Busy", "workload": 8, "availability": True},
                {"id": 2, "name": "Free", "workload": 1, "availability": True},
                {"id": 3, "name": "Away", "workload": 0, "availability": False},
            ]
        },
        headers=supervisor_headers(),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["recommendation"]["name"] == "Free"
    assert [candidate["name"] for candidate in body["ranking"]] == ["Free", "Busy"]
    assert body["active_weight_total"] == 30
    assert "geographical proximity" in body["limitations"].lower()
    assert body["ineligible_engineers"][0]["name"] == "Away"


def test_dispatch_recommendations_reject_invalid_candidates():
    response = client.post(
        "/api/dispatch/recommendations",
        json={"engineers": [{"id": 1, "name": "", "workload": -1, "availability": True}]},
        headers=supervisor_headers(),
    )

    assert response.status_code == 422


def test_engineer_crud_and_stored_profile_dispatch(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api-engineers.db'}")
    Base.metadata.create_all(engine)
    service = EngineerManagementService(DatabaseEngineerRepository(sessionmaker(bind=engine)))
    monkeypatch.setattr(app_module, "engineer_management_service", service)

    invalid = client.post(
        "/api/engineers",
        json={"id": 1, "name": "", "workload": -1, "availability": True},
        headers=supervisor_headers(),
    )
    assert invalid.status_code == 422

    assert client.post(
        "/api/engineers",
        json={"id": 1, "name": "Busy", "workload": 5, "availability": True},
        headers=supervisor_headers(),
    ).status_code == 200
    assert client.post(
        "/api/engineers",
        json={"id": 2, "name": "Away", "workload": 0, "availability": False},
        headers=supervisor_headers(),
    ).status_code == 200
    assert client.post(
        "/api/engineers",
        json={"id": 3, "name": "Free", "workload": 1, "availability": True},
        headers=supervisor_headers(),
    ).status_code == 200

    assert client.get("/api/engineers/1", headers=supervisor_headers()).json()["name"] == "Busy"
    updated = client.put(
        "/api/engineers/1",
        json={"name": "Busy Updated", "workload": 4, "availability": True},
        headers=supervisor_headers(),
    )
    assert updated.status_code == 200
    assert [engineer["id"] for engineer in client.get("/api/engineers", headers=supervisor_headers()).json()] == [1, 2, 3]

    recommendation = client.post("/api/dispatch/recommendations", json={}, headers=supervisor_headers())
    assert recommendation.status_code == 200
    body = recommendation.json()
    assert body["recommendation"]["name"] == "Free"
    assert [candidate["id"] for candidate in body["ranking"]] == [3, 1]
    assert body["ineligible_engineers"] == [{"id": 2, "name": "Away", "reason": "unavailable"}]

    selected = client.post("/api/dispatch/recommendations", json={"engineer_ids": [1, 2]}, headers=supervisor_headers())
    assert selected.status_code == 200
    assert [candidate["id"] for candidate in selected.json()["ranking"]] == [1]


def test_engineer_skills_and_completed_assignment_endpoint_feed_stored_dispatch(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api-skills.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(app_module, "engineer_management_service", EngineerManagementService(DatabaseEngineerRepository(sessionmaker(bind=engine))))

    assert client.post("/api/engineers", json={"id": 7, "name": "Nandi", "workload": 1, "availability": True, "skills": ["network", "linux"]}, headers=supervisor_headers()).status_code == 200
    outcome = client.post("/api/engineers/7/completed-assignments", json={"incident_category": "network", "required_skills": ["network"], "sla_met": True}, headers=supervisor_headers())
    assert outcome.status_code == 200

    ranked = client.post("/api/dispatch/recommendations", json={"required_skills": ["network", "linux"]}, headers=supervisor_headers())
    assert ranked.status_code == 200
    body = ranked.json()
    assert body["recommendation"]["id"] == 7
    assert body["active_weight_total"] == 80
    assert body["recommendation"]["score_breakdown"]["historical_sla_success"]["completed_assignment_count"] == 1


def test_coordinate_payloads_validate_persist_and_drive_dispatch(monkeypatch, tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'api-coordinates.db'}")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(app_module, "engineer_management_service", EngineerManagementService(DatabaseEngineerRepository(sessionmaker(bind=engine))))

    invalid = client.post("/api/engineers", json={"id": 8, "name": "Invalid", "workload": 1, "availability": True, "latitude": 91, "longitude": 28}, headers=supervisor_headers())
    assert invalid.status_code == 422
    assert client.post("/api/engineers", json={"id": 8, "name": "Near", "workload": 1, "availability": True, "latitude": -26.1050, "longitude": 28.0560}, headers=supervisor_headers()).status_code == 200
    assert client.get("/api/engineers/8", headers=supervisor_headers()).json()["latitude"] == -26.1050

    ranked = client.post("/api/dispatch/recommendations", json={"incident_latitude": -26.1076, "incident_longitude": 28.0567}, headers=supervisor_headers())
    assert ranked.status_code == 200
    assert ranked.json()["recommendation"]["score_breakdown"]["geographical_proximity"]["calculation"] == "Haversine"
