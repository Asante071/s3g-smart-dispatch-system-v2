from database import SessionLocal
from repositories.database_models import CompletedAssignmentModel, EngineerModel
from repositories.engineer_repository import EngineerRepository
from src.engineer import Engineer


class DatabaseEngineerRepository(EngineerRepository):
    """PostgreSQL-backed storage for the currently supported engineer profile."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def save(self, engineer):
        db = self.session_factory()
        try:
            record = db.get(EngineerModel, engineer.id)
            if record is None:
                record = EngineerModel(id=engineer.id)
                db.add(record)

            record.name = engineer.name
            record.workload = engineer.workload
            record.availability = engineer.availability
            record.skills = engineer.skills
            record.latitude = engineer.latitude
            record.longitude = engineer.longitude
            db.commit()
            return engineer
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def find_by_id(self, engineer_id):
        db = self.session_factory()
        try:
            record = db.get(EngineerModel, engineer_id)
            return self._to_domain(db, record) if record is not None else None
        finally:
            db.close()

    def find_all(self):
        db = self.session_factory()
        try:
            return [self._to_domain(db, record) for record in db.query(EngineerModel).order_by(EngineerModel.id).all()]
        finally:
            db.close()

    def delete(self, engineer_id):
        db = self.session_factory()
        try:
            record = db.get(EngineerModel, engineer_id)
            if record is not None:
                db.delete(record)
                db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def record_completed_assignment(self, engineer_id, assignment):
        db = self.session_factory()
        try:
            if db.get(EngineerModel, engineer_id) is None:
                return None
            record = CompletedAssignmentModel(
                engineer_id=engineer_id,
                incident_category=assignment.get("incident_category"),
                required_skills=assignment.get("required_skills", []),
                sla_met=assignment["sla_met"],
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return self._assignment_to_dict(record)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def get_completed_assignments(self, engineer_id):
        db = self.session_factory()
        try:
            records = db.query(CompletedAssignmentModel).filter_by(engineer_id=engineer_id).order_by(CompletedAssignmentModel.id).all()
            return [self._assignment_to_dict(record) for record in records]
        finally:
            db.close()

    def _to_domain(self, db, record):
        assignments = db.query(CompletedAssignmentModel).filter_by(engineer_id=record.id).order_by(CompletedAssignmentModel.id).all()
        return Engineer(record.id, record.name, record.workload, record.availability, record.skills or [], [self._assignment_to_dict(item) for item in assignments], record.latitude, record.longitude)

    @staticmethod
    def _assignment_to_dict(record):
        return {
            "id": record.id,
            "incident_category": record.incident_category,
            "required_skills": record.required_skills or [],
            "sla_met": record.sla_met,
        }
