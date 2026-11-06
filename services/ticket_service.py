from factories.repository_factory import RepositoryFactory
from src.ticket import Ticket


class TicketService:

    def __init__(self, repository=None, seed_demo_data=True):

        self.repo = repository or RepositoryFactory.get_ticket_repository(
            "MEMORY"
        )

        if seed_demo_data:
            self._seed_demo_data()

    def _seed_demo_data(self):

        demo_tickets = [
            Ticket(
                1,
                "VPN Connection Failure",
                "HIGH",
                2,
                "OPEN",
                "Sarah"
            ),
            Ticket(
                2,
                "Email Outage",
                "AMBER",
                4,
                "IN_PROGRESS",
                "David"
            ),
            Ticket(
                3,
                "Printer Offline",
                "LOW",
                8,
                "OPEN",
                "Mike"
            )
        ]

        for ticket in demo_tickets:
            if self.repo.find_by_id(ticket.id) is None:
                self.repo.save(ticket)

    def create_ticket(self, ticket):

        if ticket.risk not in ["LOW", "AMBER", "HIGH"]:
            raise ValueError("Invalid risk level")

        self.repo.save(ticket)
        return ticket

    def get_all_tickets(self):
        return self.repo.find_all()

    def get_ticket(self, id):
        return self.repo.find_by_id(id)

    def update_ticket_status(self, id, status):

        ticket = self.get_ticket(id)

        if ticket is None:
            return None

        ticket.update_status(status)
        self.repo.save(ticket)

        return ticket

    def assign_engineer(self, id, engineer):

        ticket = self.get_ticket(id)

        if ticket is None:
            return None

        ticket.assign_engineer(engineer)
        self.repo.save(ticket)

        return ticket

    def process_sla_countdown(self):

        tickets = self.repo.find_all()

        for ticket in tickets:

            if ticket.status != "CLOSED" and ticket.sla_remaining > 0:
                ticket.sla_remaining -= 1
                self.repo.save(ticket)
