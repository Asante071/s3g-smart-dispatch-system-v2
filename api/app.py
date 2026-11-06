
import os
from typing import Literal

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import text

from database import BASE_DIR, Base, engine
from factories.repository_factory import RepositoryFactory
from services.sla_prediction_service import SLAPredictionService
from services.prediction_audit_service import PredictionAuditService
from services.ticket_service import TicketService
from services.dispatch_recommendation_service import DispatchRecommendationService
from services.routing_service import RoutingService
from services.engineer_management_service import EngineerManagementService
from services.auth_service import AuthService
from repositories.database_user_repository import DatabaseUserRepository
from src.engineer import Engineer
from src.ticket import Ticket
from src.user import ROLE_EMPLOYEE, ROLE_SUPERVISOR, ROLE_TECHNICIAN


load_dotenv(BASE_DIR / ".env")

storage_type = os.getenv("STORAGE_TYPE", "MEMORY").upper()
FRONTEND_DIR = BASE_DIR / "frontend"

repository = RepositoryFactory.get_ticket_repository(storage_type)

sla_prediction_service = SLAPredictionService()
prediction_audit_service = PredictionAuditService()
dispatch_recommendation_service = DispatchRecommendationService(
    routing_service=RoutingService()
)
engineer_management_service = EngineerManagementService()
user_service = AuthService(DatabaseUserRepository())

# Create additive persistence tables when the application starts against PostgreSQL.
from repositories.database_models import CompletedAssignmentModel, EngineerModel, PredictionAuditModel, TicketModel, UserModel
Base.metadata.create_all(
    bind=engine,
    tables=[
        PredictionAuditModel.__table__, EngineerModel.__table__,
        CompletedAssignmentModel.__table__, TicketModel.__table__, UserModel.__table__,
    ],
)
# create_all is intentionally non-destructive, but it does not add a column to
# an existing PostgreSQL engineers table. Keep this one additive migration next
# to the startup schema setup so installations from the prior milestone retain
# their profiles and gain an empty skills list.
if engine.dialect.name == "postgresql":
    with engine.begin() as connection:
        connection.execute(text(
            "ALTER TABLE engineers ADD COLUMN IF NOT EXISTS skills JSON NOT NULL DEFAULT '[]'::json"
        ))
        connection.execute(text("ALTER TABLE engineers ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE engineers ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION"))
        connection.execute(text("ALTER TABLE tickets ADD COLUMN IF NOT EXISTS reporter_email VARCHAR(255)"))

user_service.ensure_demo_users()
# Schema upgrades must precede ticket-service demo seeding: existing PostgreSQL
# tables need the additive reporter column before the repository reads them.
ticket_service = TicketService(repository=repository)


app = FastAPI(
    title="S³G Smart Dispatch System",
    description="""
## Intelligent IT Service Management Platform

The S³G Smart Dispatch System provides:

- Incident Ticket Management
- SLA Monitoring
- Smart Dispatch Workflows
- REST API Integration
- Service Layer Processing
- Repository-Based Data Management

### Software Engineering Features

- FastAPI REST API
- Repository Pattern
- Service Layer Architecture
- Automated Testing with Pytest
- CI/CD with GitHub Actions
- Open Source Collaboration Support
""",
    version="1.0.0",
    contact={
        "name": "Asante Seotsanyana",
        "url": "https://github.com/Asante071"
    },
    license_info={
        "name": "MIT License"
    }
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
):
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid company login is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = user_service.user_from_token(credentials.credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your company login is invalid or has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_roles(*allowed_roles):
    def role_dependency(user=Depends(get_current_user)):
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your company role is not permitted to perform this action",
            )
        return user

    return role_dependency


def ticket_is_visible_to_user(ticket, user):
    if user.role == ROLE_SUPERVISOR:
        return True
    if user.role == ROLE_EMPLOYEE:
        return (ticket.reporter_email or "").casefold() == user.email
    return (ticket.engineer or "").casefold() == user.display_name.casefold()


def get_visible_ticket_or_raise(ticket_id, user):
    ticket = ticket_service.get_ticket(ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
    if not ticket_is_visible_to_user(ticket, user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not permitted to access this ticket")
    return ticket


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=1, max_length=256)


class TicketRequest(BaseModel):
    # IDs remain accepted for compatibility with the existing API. The employee
    # portal omits them and receives the next available incident number.
    id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=255)
    priority: str
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    model_config = {
        "json_schema_extra": {
            "example": {
                "id": 1,
                "title": "VPN Connection Failure",
                "priority": "HIGH"
            }
        }
    }


class StatusUpdateRequest(BaseModel):
    status: Literal["OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"]


class EngineerAssignmentRequest(BaseModel):
    engineer: str


class EngineerRecommendationCandidate(BaseModel):
    id: int
    name: str = Field(min_length=1)
    workload: float = Field(ge=0)
    availability: bool
    skills: list[str] = Field(default_factory=list)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class EngineerRequest(BaseModel):
    id: int
    name: str = Field(min_length=1, max_length=100)
    workload: float = Field(ge=0)
    availability: bool
    skills: list[str] = Field(default_factory=list)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class EngineerUpdateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    workload: float = Field(ge=0)
    availability: bool
    skills: list[str] = Field(default_factory=list)
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)


class CompletedAssignmentRequest(BaseModel):
    incident_category: str | None = Field(default=None, min_length=1, max_length=100)
    required_skills: list[str] = Field(default_factory=list)
    sla_met: bool


class DispatchRecommendationRequest(BaseModel):
    engineers: list[EngineerRecommendationCandidate] | None = None
    engineer_ids: list[int] | None = Field(default=None, min_length=1)
    incident_category: str | None = Field(default=None, min_length=1, max_length=100)
    required_skills: list[str] = Field(default_factory=list)
    incident_latitude: float | None = Field(default=None, ge=-90, le=90)
    incident_longitude: float | None = Field(default=None, ge=-180, le=180)


class SLAPredictionRequest(BaseModel):
    # A technician must identify an incident from their own queue.  The field
    # is intentionally optional for supervisors, who can run scenario checks
    # as part of company-wide SLA oversight.
    ticket_id: int | None = Field(default=None, ge=1)
    priority: str
    category: str
    complexity: float
    engineer_experience: float
    engineer_workload: float
    previous_incidents: float
    sla_allowed_hours: float
    incident_age_hours: float
    sla_remaining_hours: float

    model_config = {
        "json_schema_extra": {
            "example": {
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
        }
    }


@app.post("/api/auth/login", tags=["Authentication"], summary="Sign in with a simulated company account")
def login(request: LoginRequest):
    user = user_service.authenticate(request.email, request.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "access_token": user_service.issue_token(user),
        "token_type": "bearer",
        "expires_in": user_service.TOKEN_LIFETIME_SECONDS,
        "user": {"email": user.email, "display_name": user.display_name, "role": user.role},
    }


@app.get("/api/auth/me", tags=["Authentication"], summary="Get the active company session")
def get_authenticated_user(user=Depends(get_current_user)):
    return {"email": user.email, "display_name": user.display_name, "role": user.role}


@app.post(
    "/api/predict",
    tags=["SLA Prediction"],
    summary="Predict SLA breach risk",
    description=(
        "Predicts SLA breach risk from the trained model. Model performance is "
        "based on synthetic IT incident data."
    ),
)
def predict_sla_breach(
    request: SLAPredictionRequest,
    user=Depends(require_roles(ROLE_TECHNICIAN, ROLE_SUPERVISOR)),
):
    if user.role == ROLE_TECHNICIAN:
        if request.ticket_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Technicians must select an incident assigned to them",
            )
        get_visible_ticket_or_raise(request.ticket_id, user)

    # ticket_id scopes authorization for technicians.  Prediction audit rows
    # retain their established schema of the model's nine input features.
    incident = request.model_dump(exclude={"ticket_id"})
    prediction = sla_prediction_service.predict(incident)
    prediction_audit_service.record(incident, prediction)
    return prediction


@app.get(
    "/api/predictions",
    tags=["SLA Prediction"],
    summary="Retrieve recent SLA predictions",
)
def get_recent_predictions(
    limit: int = Query(default=20, ge=1, le=100),
    user=Depends(require_roles(ROLE_SUPERVISOR)),
):
    return prediction_audit_service.get_recent(limit)


@app.get("/api/dashboard/employee", tags=["Dashboards"], summary="View an employee's own incident portal")
def get_employee_dashboard(user=Depends(require_roles(ROLE_EMPLOYEE))):
    tickets = [ticket for ticket in ticket_service.get_all_tickets() if ticket_is_visible_to_user(ticket, user)]
    return {
        "tickets": tickets,
        "summary": {
            "total": len(tickets),
            "open": sum(ticket.status != "CLOSED" for ticket in tickets),
            "at_risk": sum(ticket.sla_remaining <= 2 and ticket.status != "CLOSED" for ticket in tickets),
        },
    }


@app.get("/api/dashboard/technician", tags=["Dashboards"], summary="View a technician's assigned incidents and workload")
def get_technician_dashboard(user=Depends(require_roles(ROLE_TECHNICIAN))):
    tickets = [ticket for ticket in ticket_service.get_all_tickets() if ticket_is_visible_to_user(ticket, user)]
    engineer_profile = next(
        (
            engineer for engineer in engineer_management_service.get_all_engineers()
            if engineer.name.casefold() == user.display_name.casefold()
        ),
        None,
    )
    return {
        "tickets": tickets,
        "workload": engineer_profile.workload if engineer_profile is not None else len(tickets),
        "availability": engineer_profile.availability if engineer_profile is not None else True,
        "summary": {
            "assigned": len(tickets),
            "in_progress": sum(ticket.status == "IN_PROGRESS" for ticket in tickets),
            "at_risk": sum(ticket.sla_remaining <= 2 and ticket.status != "CLOSED" for ticket in tickets),
        },
    }


@app.get("/api/dashboard/supervisor", tags=["Dashboards"], summary="View company-wide dispatch oversight")
def get_supervisor_dashboard(user=Depends(require_roles(ROLE_SUPERVISOR))):
    tickets = ticket_service.get_all_tickets()
    engineers = engineer_management_service.get_all_engineers()
    workload = []
    for engineer in engineers:
        assigned = sum(
            (ticket.engineer or "").casefold() == engineer.name.casefold()
            for ticket in tickets
        )
        workload.append({
            "id": engineer.id,
            "name": engineer.name,
            "workload": engineer.workload,
            "availability": engineer.availability,
            "assigned_incidents": assigned,
        })

    status_breakdown = {}
    for ticket in tickets:
        status_breakdown[ticket.status] = status_breakdown.get(ticket.status, 0) + 1
    return {
        "tickets": tickets,
        "engineer_workload": workload,
        "recent_predictions": prediction_audit_service.get_recent(10),
        "analytics": {
            "total_incidents": len(tickets),
            "open_incidents": sum(ticket.status != "CLOSED" for ticket in tickets),
            "critical_incidents": sum(ticket.risk == "HIGH" for ticket in tickets),
            "at_risk_incidents": sum(ticket.sla_remaining <= 2 and ticket.status != "CLOSED" for ticket in tickets),
            "status_breakdown": status_breakdown,
        },
    }


@app.post(
    "/api/dispatch/recommendations",
    tags=["Dispatch"],
    summary="Rank eligible engineers for dispatch",
    description=(
     "Ranks eligible engineers using workload, availability, "
     "technical expertise, historical SLA performance, geographical "
     "proximity and estimated OSRM road travel time when supporting "
     "data is available. Unavailable criteria are reported explicitly."
    ),
)
def recommend_engineers(
    request: DispatchRecommendationRequest,
    user=Depends(require_roles(ROLE_SUPERVISOR)),
):
    if request.engineers is not None and request.engineer_ids is not None:
        raise HTTPException(status_code=422, detail="Provide engineers or engineer_ids, not both")

    if request.engineers is not None:
        engineers = [
            Engineer(candidate.id, candidate.name, candidate.workload, candidate.availability, candidate.skills,
                     latitude=candidate.latitude, longitude=candidate.longitude)
            for candidate in request.engineers
        ]
    elif request.engineer_ids is not None:
        engineers = []
        for engineer_id in request.engineer_ids:
            engineer = engineer_management_service.get_engineer(engineer_id)
            if engineer is None:
                raise HTTPException(status_code=404, detail=f"Engineer {engineer_id} not found")
            engineers.append(engineer)
    else:
        engineers = engineer_management_service.get_all_engineers()

    return dispatch_recommendation_service.recommend(
        engineers, required_skills=request.required_skills, incident_category=request.incident_category,
        incident_latitude=request.incident_latitude, incident_longitude=request.incident_longitude
    )


@app.post("/api/engineers", tags=["Engineers"], summary="Create an engineer profile")
def create_engineer(
    request: EngineerRequest,
    user=Depends(require_roles(ROLE_SUPERVISOR)),
):
    try:
        return engineer_management_service.create_engineer(
            Engineer(request.id, request.name, request.workload, request.availability, request.skills,
                     latitude=request.latitude, longitude=request.longitude)
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/engineers", tags=["Engineers"], summary="Retrieve all engineer profiles")
def get_engineers(user=Depends(require_roles(ROLE_SUPERVISOR))):
    return engineer_management_service.get_all_engineers()


@app.get("/api/engineers/{engineer_id}", tags=["Engineers"], summary="Retrieve an engineer profile")
def get_engineer(
    engineer_id: int,
    user=Depends(require_roles(ROLE_SUPERVISOR)),
):
    engineer = engineer_management_service.get_engineer(engineer_id)
    if engineer is None:
        raise HTTPException(status_code=404, detail="Engineer not found")
    return engineer


@app.put("/api/engineers/{engineer_id}", tags=["Engineers"], summary="Update an engineer profile")
def update_engineer(
    engineer_id: int,
    request: EngineerUpdateRequest,
    user=Depends(require_roles(ROLE_SUPERVISOR)),
):
    coordinate_updates = {}
    if "latitude" in request.model_fields_set:
        coordinate_updates["latitude"] = request.latitude
    if "longitude" in request.model_fields_set:
        coordinate_updates["longitude"] = request.longitude
    engineer = engineer_management_service.update_engineer(
        engineer_id, request.name, request.workload, request.availability, request.skills,
        **coordinate_updates,
    )
    if engineer is None:
        raise HTTPException(status_code=404, detail="Engineer not found")
    return engineer


@app.post("/api/engineers/{engineer_id}/completed-assignments", tags=["Engineers"], summary="Record a completed assignment SLA outcome")
def record_completed_assignment(
    engineer_id: int,
    request: CompletedAssignmentRequest,
    user=Depends(require_roles(ROLE_SUPERVISOR)),
):
    try:
        outcome = engineer_management_service.record_completed_assignment(engineer_id, request.model_dump())
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
    if outcome is None:
        raise HTTPException(status_code=404, detail="Engineer not found")
    return outcome


@app.get(
    "/api/tickets",
    tags=["Tickets"],
    summary="Retrieve all tickets",
    description="Returns all incident tickets currently stored in the system."
)
def get_tickets(user=Depends(get_current_user)):
    return [
        ticket for ticket in ticket_service.get_all_tickets()
        if ticket_is_visible_to_user(ticket, user)
    ]


@app.get(
    "/api/tickets/{ticket_id}",
    tags=["Tickets"],
    summary="Retrieve a ticket by ID",
    description="Returns detailed information about a specific incident ticket."
)
def get_ticket(ticket_id: int, user=Depends(get_current_user)):
    return get_visible_ticket_or_raise(ticket_id, user)


@app.post(
    "/api/tickets",
    tags=["Tickets"],
    summary="Create a new incident ticket",
    description="Creates a new support ticket and stores it through the service layer."
)
def create_ticket(
    ticket_request: TicketRequest,
    user=Depends(require_roles(ROLE_EMPLOYEE)),
):
    ticket_id = ticket_request.id
    if ticket_id is None:
        existing_ids = [ticket.id for ticket in ticket_service.get_all_tickets()]
        ticket_id = max(existing_ids, default=0) + 1
    elif ticket_service.get_ticket(ticket_id) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A ticket with this ID already exists")

    ticket = Ticket(
        ticket_id,
        ticket_request.title,
        ticket_request.priority.upper(),
        2,
        "OPEN",
        latitude=ticket_request.latitude,
        longitude=ticket_request.longitude,
        reporter_email=user.email,
    )

    return ticket_service.create_ticket(ticket)


@app.put("/api/tickets/{ticket_id}/status")
def update_ticket_status(
    ticket_id: int,
    request: StatusUpdateRequest,
    user=Depends(require_roles(ROLE_TECHNICIAN, ROLE_SUPERVISOR)),
):
    get_visible_ticket_or_raise(ticket_id, user)
    ticket = ticket_service.update_ticket_status(
        ticket_id,
        request.status
    )

    return ticket


@app.put("/api/tickets/{ticket_id}/assign")
def assign_engineer(
    ticket_id: int,
    request: EngineerAssignmentRequest,
    user=Depends(require_roles(ROLE_SUPERVISOR)),
):
    get_visible_ticket_or_raise(ticket_id, user)
    ticket = ticket_service.assign_engineer(
        ticket_id,
        request.engineer
    )

    return ticket


@app.post("/api/process-sla")
def process_sla(user=Depends(require_roles(ROLE_SUPERVISOR))):

    ticket_service.process_sla_countdown()

    return {
        "message": "SLA countdown processed"
    }


# Mount the existing browser portal after API routes so a same-origin frontend
# can safely send authenticated requests to /api regardless of its local port.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
