class InMemoryUserRepository:
    """In-memory user store used by authorization tests and local prototypes."""

    def __init__(self):
        self.users = {}
        self._next_id = 1

    def save(self, user):
        existing = self.users.get(user.email)
        if existing is None:
            user.id = self._next_id
            self._next_id += 1
        else:
            user.id = existing.id
        self.users[user.email] = user
        return user

    def find_by_email(self, email):
        return self.users.get(email)
