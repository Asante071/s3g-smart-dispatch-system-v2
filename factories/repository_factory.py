from repositories.database_ticket_repository import DatabaseTicketRepository
from repositories.database_engineer_repository import DatabaseEngineerRepository
from repositories.inmemory.inmemory_ticket_repository import InMemoryTicketRepository


class RepositoryFactory:

    @staticmethod
    def get_ticket_repository(storage_type="MEMORY"):

        storage_type = storage_type.upper()

        if storage_type == "MEMORY":
            return InMemoryTicketRepository()

        if storage_type == "POSTGRES":
            return DatabaseTicketRepository()

        raise ValueError(
            f"Invalid storage type: {storage_type}"
        )

    @staticmethod
    def get_engineer_repository(storage_type="POSTGRES"):
        storage_type = storage_type.upper()
        if storage_type == "POSTGRES":
            return DatabaseEngineerRepository()
        raise ValueError(f"Invalid engineer storage type: {storage_type}")
