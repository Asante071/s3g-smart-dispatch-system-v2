from repositories.database_engineer_repository import DatabaseEngineerRepository
from src.engineer import Engineer

_UNSET = object()


class EngineerManagementService:
    """Validates and manages persistent engineer profiles."""

    def __init__(self, repository=None):
        self.repo = repository or DatabaseEngineerRepository()

    def create_engineer(self, engineer):
        self._validate(engineer)
        if self.repo.find_by_id(engineer.id) is not None:
            raise ValueError("Engineer already exists")
        return self.repo.save(engineer)

    def get_engineer(self, engineer_id):
        return self.repo.find_by_id(engineer_id)

    def get_all_engineers(self):
        return self.repo.find_all()

    def update_engineer(self, engineer_id, name, workload, availability, skills=None, latitude=_UNSET, longitude=_UNSET):
        engineer = self.repo.find_by_id(engineer_id)
        if engineer is None:
            return None
        engineer.name = name
        engineer.workload = workload
        engineer.availability = availability
        if skills is not None:
            engineer.skills = skills
        if latitude is not _UNSET:
            engineer.latitude = latitude
        if longitude is not _UNSET:
            engineer.longitude = longitude
        self._validate(engineer)
        return self.repo.save(engineer)

    def record_completed_assignment(self, engineer_id, assignment):
        if self.repo.find_by_id(engineer_id) is None:
            return None
        self._validate_assignment(assignment)
        return self.repo.record_completed_assignment(engineer_id, assignment)

    @staticmethod
    def _validate(engineer):
        if not engineer.name or not engineer.name.strip():
            raise ValueError("Engineer name is required")
        if engineer.workload < 0:
            raise ValueError("Engineer workload cannot be negative")
        if any(not isinstance(skill, str) or not skill.strip() for skill in engineer.skills):
            raise ValueError("Engineer skills must be non-empty strings")
        EngineerManagementService._validate_coordinates(engineer.latitude, engineer.longitude)

    @staticmethod
    def _validate_coordinates(latitude, longitude):
        if (latitude is None) != (longitude is None):
            raise ValueError("Latitude and longitude must be provided together")
        if latitude is not None and not -90 <= latitude <= 90:
            raise ValueError("Latitude must be between -90 and 90")
        if longitude is not None and not -180 <= longitude <= 180:
            raise ValueError("Longitude must be between -180 and 180")

    @staticmethod
    def _validate_assignment(assignment):
        if not isinstance(assignment.get("sla_met"), bool):
            raise ValueError("Completed assignment must state whether SLA was met")
        if any(not isinstance(skill, str) or not skill.strip() for skill in assignment.get("required_skills", [])):
            raise ValueError("Assignment skills must be non-empty strings")
