from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, func

from database import Base


class TicketModel(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    issue = Column(String(255), nullable=False)
    risk = Column(String(20), nullable=False)
    sla_remaining = Column(Float, nullable=False)
    status = Column(String(30), nullable=False)
    engineer = Column(
        String(100),
        nullable=False,
        default="Unassigned",
    )
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    reporter_email = Column(String(255), nullable=True, index=True)


class UserModel(Base):
    """Company account used by the role-protected prototype."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), nullable=False, unique=True, index=True)
    display_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, index=True)
    password_salt = Column(String(255), nullable=False)
    password_hash = Column(String(255), nullable=False)


class EngineerModel(Base):
    """Persistent profile for the dispatch fields supported today."""

    __tablename__ = "engineers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    workload = Column(Float, nullable=False, default=0)
    availability = Column(Boolean, nullable=False, default=True)
    skills = Column(JSON, nullable=False, default=list)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)


class CompletedAssignmentModel(Base):
    """An observed completed assignment used for SLA-success reporting."""

    __tablename__ = "completed_assignments"

    id = Column(Integer, primary_key=True, index=True)
    engineer_id = Column(Integer, ForeignKey("engineers.id"), nullable=False, index=True)
    incident_category = Column(String(100), nullable=True)
    required_skills = Column(JSON, nullable=False, default=list)
    sla_met = Column(Boolean, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class PredictionAuditModel(Base):
    """Immutable record of an SLA model prediction."""

    __tablename__ = "prediction_audits"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    model_version = Column(String(80), nullable=False)
    priority = Column(String(20), nullable=False)
    category = Column(String(100), nullable=False)
    complexity = Column(Float, nullable=False)
    engineer_experience = Column(Float, nullable=False)
    engineer_workload = Column(Float, nullable=False)
    previous_incidents = Column(Float, nullable=False)
    sla_allowed_hours = Column(Float, nullable=False)
    incident_age_hours = Column(Float, nullable=False)
    sla_remaining_hours = Column(Float, nullable=False)
    breach_probability = Column(Float, nullable=False)
    risk_level = Column(String(20), nullable=False)
    high_risk_threshold = Column(Float, nullable=False)
