import pytest

from services.engineer_management_service import EngineerManagementService
from src.engineer import Engineer


class InMemoryEngineerRepository:
    def __init__(self):
        self.items = {}

    def save(self, engineer):
        self.items[engineer.id] = engineer
        return engineer

    def find_by_id(self, engineer_id):
        return self.items.get(engineer_id)

    def find_all(self):
        return list(self.items.values())

    def delete(self, engineer_id):
        self.items.pop(engineer_id, None)


def test_engineer_service_rejects_duplicate_and_negative_workload():
    service = EngineerManagementService(InMemoryEngineerRepository())
    service.create_engineer(Engineer(1, "Sarah", 2, True))

    with pytest.raises(ValueError, match="already exists"):
        service.create_engineer(Engineer(1, "Sarah", 2, True))

    with pytest.raises(ValueError, match="cannot be negative"):
        service.create_engineer(Engineer(2, "David", -1, True))


def test_engineer_service_requires_complete_and_in_range_coordinate_pairs():
    service = EngineerManagementService(InMemoryEngineerRepository())

    with pytest.raises(ValueError, match="provided together"):
        service.create_engineer(Engineer(3, "Lebo", 1, True, latitude=-26.1))
    with pytest.raises(ValueError, match="Latitude"):
        service.create_engineer(Engineer(4, "Lebo", 1, True, latitude=91, longitude=28.0))

    saved = service.create_engineer(Engineer(5, "Lebo", 1, True, latitude=-26.1, longitude=28.0))
    updated = service.update_engineer(5, "Lebo", 2, True)
    assert (saved.latitude, saved.longitude) == (-26.1, 28.0)
    assert (updated.latitude, updated.longitude) == (-26.1, 28.0)
