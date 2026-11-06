import importlib

from fastapi.testclient import TestClient

from repositories.inmemory.inmemory_ticket_repository import InMemoryTicketRepository
from repositories.inmemory.inmemory_user_repository import InMemoryUserRepository
from services.auth_service import AuthService
from services.ticket_service import TicketService
from src.ticket import Ticket


app_module = importlib.import_module("api.app")
client = TestClient(app_module.app)


class EmptyEngineerService:
    def get_all_engineers(self):
        return []


class EmptyPredictionAuditService:
    def record(self, incident, prediction):
        return None

    def get_recent(self, limit):
        return []


def make_headers(email):
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "TestOnly!Passphrase"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def isolated_role_services(monkeypatch):
    users = AuthService(InMemoryUserRepository(), token_secret="authorization-test-secret")
    for email, name, role in (
        ("employee.one@s3g.local", "Employee One", "EMPLOYEE"),
        ("employee.two@s3g.local", "Employee Two", "EMPLOYEE"),
        ("sarah.test@s3g.local", "Sarah", "TECHNICIAN"),
        ("david.test@s3g.local", "David", "TECHNICIAN"),
        ("supervisor.test@s3g.local", "Supervisor", "SUPERVISOR"),
    ):
        users.create_user(email, name, role, "TestOnly!Passphrase")

    tickets = TicketService(InMemoryTicketRepository(), seed_demo_data=False)
    tickets.create_ticket(Ticket(41, "Employee one incident", "HIGH", 2, "OPEN", reporter_email="employee.one@s3g.local"))
    tickets.create_ticket(Ticket(42, "Employee two incident", "LOW", 8, "OPEN", reporter_email="employee.two@s3g.local"))
    tickets.create_ticket(Ticket(43, "Sarah assignment", "AMBER", 4, "IN_PROGRESS", engineer="Sarah"))
    monkeypatch.setattr(app_module, "user_service", users)
    monkeypatch.setattr(app_module, "ticket_service", tickets)
    monkeypatch.setattr(app_module, "engineer_management_service", EmptyEngineerService())
    monkeypatch.setattr(app_module, "prediction_audit_service", EmptyPredictionAuditService())
    return users


def test_passwords_are_salted_hashes_and_login_rejects_bad_credentials(monkeypatch):
    users = isolated_role_services(monkeypatch)
    stored = users.repository.find_by_email("employee.one@s3g.local")

    assert stored.password_hash != "TestOnly!Passphrase"
    assert stored.password_salt != "TestOnly!Passphrase"
    assert client.post("/api/auth/login", json={"email": stored.email, "password": "wrong"}).status_code == 401
    assert client.get("/api/tickets").status_code == 401


def test_demo_supervisor_role_is_reconciled_without_replacing_credentials():
    repository = InMemoryUserRepository()
    users = AuthService(repository, token_secret="authorization-test-secret")
    users.create_user("supervisor@s3g.local", "Old label", "EMPLOYEE", "DispatchDemo!2026")
    before = repository.find_by_email("supervisor@s3g.local")

    users.ensure_demo_users()

    supervisor = repository.find_by_email("supervisor@s3g.local")
    assert supervisor.role == "SUPERVISOR"
    assert supervisor.display_name == "Sam Supervisor"
    assert supervisor.password_hash == before.password_hash
    assert supervisor.password_salt == before.password_salt


def test_employee_can_only_create_and_view_own_tickets(monkeypatch):
    isolated_role_services(monkeypatch)
    employee = make_headers("employee.one@s3g.local")

    listed = client.get("/api/tickets", headers=employee)
    assert listed.status_code == 200
    assert [ticket["id"] for ticket in listed.json()] == [41]

    created = client.post(
        "/api/tickets",
        json={"title": "Zebra employee-created incident", "priority": "HIGH"},
        headers=employee,
    )
    assert created.status_code == 200
    assert created.json()["reporter_email"] == "employee.one@s3g.local"
    # This guards the browser regression where an incident title appeared to
    # lose its first character after submission.
    assert created.json()["issue"] == "Zebra employee-created incident"
    assert client.get("/api/tickets/42", headers=employee).status_code == 403
    assert client.put("/api/tickets/43/status", json={"status": "CLOSED"}, headers=employee).status_code == 403
    assert client.get("/api/engineers", headers=employee).status_code == 403
    assert client.get("/api/predictions", headers=employee).status_code == 403
    assert client.get("/api/dashboard/supervisor", headers=employee).status_code == 403
    assert client.post(
        "/api/dispatch/recommendations",
        json={"required_skills": []},
        headers=employee,
    ).status_code == 403


def test_technician_is_limited_to_assigned_incidents_and_supervisor_has_oversight(monkeypatch):
    isolated_role_services(monkeypatch)
    technician = make_headers("sarah.test@s3g.local")
    supervisor = make_headers("supervisor.test@s3g.local")

    listed = client.get("/api/tickets", headers=technician)
    assert listed.status_code == 200
    assert [ticket["id"] for ticket in listed.json()] == [43]
    assert client.put("/api/tickets/43/status", json={"status": "RESOLVED"}, headers=technician).status_code == 200
    assert client.put("/api/tickets/42/status", json={"status": "CLOSED"}, headers=technician).status_code == 403
    assert client.get("/api/predictions", headers=technician).status_code == 403
    assert client.get("/api/dashboard/supervisor", headers=technician).status_code == 403
    assert client.put("/api/tickets/42/assign", json={"engineer": "Sarah"}, headers=technician).status_code == 403
    assert client.post(
        "/api/dispatch/recommendations",
        json={"required_skills": []},
        headers=technician,
    ).status_code == 403
    prediction = {
        "priority": "HIGH", "category": "Network", "complexity": 8,
        "engineer_experience": 2, "engineer_workload": 4,
        "previous_incidents": 1, "sla_allowed_hours": 8,
        "incident_age_hours": 2, "sla_remaining_hours": 6,
    }
    assert client.post("/api/predict", json=prediction, headers=technician).status_code == 422
    assert client.post(
        "/api/predict", json={**prediction, "ticket_id": 42}, headers=technician,
    ).status_code == 403
    assert client.post(
        "/api/predict", json={**prediction, "ticket_id": 43}, headers=technician,
    ).status_code == 200

    all_tickets = client.get("/api/tickets", headers=supervisor)
    assert all_tickets.status_code == 200
    assert {ticket["id"] for ticket in all_tickets.json()} == {41, 42, 43}
    assert client.put("/api/tickets/42/assign", json={"engineer": "David"}, headers=supervisor).status_code == 200
    dashboard = client.get("/api/dashboard/supervisor", headers=supervisor)
    assert dashboard.status_code == 200
    assert dashboard.json()["analytics"]["total_incidents"] == 3
