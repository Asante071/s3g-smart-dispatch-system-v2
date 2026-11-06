class Ticket:

    def __init__(
        self,
        id,
        issue,
        risk,
        sla_remaining,
        status,
        engineer="Unassigned",
        latitude=None,
        longitude=None,
        reporter_email=None,
    ):
        self.id = id
        self.issue = issue
        self.risk = risk
        self.sla_remaining = sla_remaining
        self.status = status
        self.engineer = engineer
        self.latitude = latitude
        self.longitude = longitude
        # Kept optional so existing tickets and backup-era callers remain valid.
        # New employee-created tickets receive the authenticated reporter email.
        self.reporter_email = reporter_email

    def update_status(self, status):
        self.status = status

    def assign_engineer(self, engineer):
        self.engineer = engineer

    def calculate_sla(self):
        return self.sla_remaining
