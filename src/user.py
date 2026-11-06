from dataclasses import dataclass


ROLE_EMPLOYEE = "EMPLOYEE"
ROLE_TECHNICIAN = "TECHNICIAN"
ROLE_SUPERVISOR = "SUPERVISOR"
VALID_ROLES = frozenset({ROLE_EMPLOYEE, ROLE_TECHNICIAN, ROLE_SUPERVISOR})


@dataclass
class User:
    email: str
    display_name: str
    role: str
    password_salt: str
    password_hash: str
    id: int | None = None
