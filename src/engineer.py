class Engineer:
    def __init__(self, id, name, workload, availability, skills=None, completed_assignments=None,
                 latitude=None, longitude=None):
        self.id = id
        self.name = name
        self.workload = workload
        self.availability = availability
        self.skills = skills or []
        self.completed_assignments = completed_assignments or []
        self.latitude = latitude
        self.longitude = longitude

    def assign_task(self):
        self.workload += 1

    def update_availability(self, status):
        self.availability = status
