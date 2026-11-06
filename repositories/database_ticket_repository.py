from database import SessionLocal
from repositories.database_models import TicketModel
from repositories.ticket_repository import TicketRepository
from src.ticket import Ticket


class DatabaseTicketRepository(TicketRepository):

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def save(self, ticket):
        db = self.session_factory()

        try:
            record = db.get(TicketModel, ticket.id)

            if record is None:
                record = TicketModel(id=ticket.id)
                db.add(record)

            record.issue = ticket.issue
            record.risk = ticket.risk
            record.sla_remaining = ticket.sla_remaining
            record.status = ticket.status
            record.engineer = ticket.engineer
            record.latitude = ticket.latitude
            record.longitude = ticket.longitude
            record.reporter_email = ticket.reporter_email

            db.commit()
            return ticket

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()

    def find_by_id(self, id):
        db = self.session_factory()

        try:
            record = db.get(TicketModel, id)

            if record is None:
                return None

            return Ticket(
                id=record.id,
                issue=record.issue,
                risk=record.risk,
                sla_remaining=record.sla_remaining,
                status=record.status,
                engineer=record.engineer,
                latitude=record.latitude,
                longitude=record.longitude,
                reporter_email=record.reporter_email,
            )

        finally:
            db.close()

    def find_all(self):
        db = self.session_factory()

        try:
            records = db.query(TicketModel).all()

            return [
                Ticket(
                    id=record.id,
                    issue=record.issue,
                    risk=record.risk,
                    sla_remaining=record.sla_remaining,
                    status=record.status,
                    engineer=record.engineer,
                    latitude=record.latitude,
                    longitude=record.longitude,
                    reporter_email=record.reporter_email,
                )
                for record in records
            ]

        finally:
            db.close()

    def delete(self, id):
        db = self.session_factory()

        try:
            record = db.get(TicketModel, id)

            if record is not None:
                db.delete(record)
                db.commit()

        except Exception:
            db.rollback()
            raise

        finally:
            db.close()
