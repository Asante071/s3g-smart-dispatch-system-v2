from abc import ABC, abstractmethod


class EngineerRepository(ABC):
    @abstractmethod
    def save(self, engineer):
        pass

    @abstractmethod
    def find_by_id(self, engineer_id):
        pass

    @abstractmethod
    def find_all(self):
        pass

    @abstractmethod
    def delete(self, engineer_id):
        pass

    @abstractmethod
    def record_completed_assignment(self, engineer_id, assignment):
        pass

    @abstractmethod
    def get_completed_assignments(self, engineer_id):
        pass
