from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from repositories.database_engineer_repository import DatabaseEngineerRepository
from src.engineer import Engineer


def test_database_engineer_repository_persists_and_updates_profiles(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'engineers.db'}")
    Base.metadata.create_all(engine)
    repository = DatabaseEngineerRepository(sessionmaker(bind=engine))

    repository.save(Engineer(7, "Sarah", 2, True))
    saved = repository.find_by_id(7)
    assert (saved.id, saved.name, saved.workload, saved.availability) == (7, "Sarah", 2, True)

    repository.save(Engineer(7, "Sarah Jones", 4, False))
    assert [(engineer.name, engineer.workload, engineer.availability) for engineer in repository.find_all()] == [
        ("Sarah Jones", 4, False)
    ]


def test_database_engineer_repository_persists_skills_and_real_completed_outcomes(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'skills.db'}")
    Base.metadata.create_all(engine)
    repository = DatabaseEngineerRepository(sessionmaker(bind=engine))

    repository.save(Engineer(9, "Nandi", 1, True, ["Network", "Linux"]))
    recorded = repository.record_completed_assignment(9, {
        "incident_category": "Network", "required_skills": ["network"], "sla_met": True,
    })

    assert recorded["sla_met"] is True
    engineer = repository.find_by_id(9)
    assert engineer.skills == ["Network", "Linux"]
    assert engineer.completed_assignments == [recorded]


def test_database_engineer_repository_persists_coordinates(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'coordinates.db'}")
    Base.metadata.create_all(engine)
    repository = DatabaseEngineerRepository(sessionmaker(bind=engine))

    repository.save(Engineer(10, "Lebo", 1, True, latitude=-26.1050, longitude=28.0560))

    engineer = repository.find_by_id(10)
    assert (engineer.latitude, engineer.longitude) == (-26.1050, 28.0560)
