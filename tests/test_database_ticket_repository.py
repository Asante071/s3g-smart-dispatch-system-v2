from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base
from repositories.database_ticket_repository import DatabaseTicketRepository
from src.ticket import Ticket


def test_database_ticket_repository_persists_incident_coordinates(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'tickets.db'}")
    Base.metadata.create_all(engine)
    repository = DatabaseTicketRepository(sessionmaker(bind=engine))

    repository.save(Ticket(1, "Router fault", "HIGH", 2, "OPEN", latitude=-26.1076, longitude=28.0567))

    ticket = repository.find_by_id(1)
    assert (ticket.latitude, ticket.longitude) == (-26.1076, 28.0567)
