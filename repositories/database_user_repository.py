from database import SessionLocal
from repositories.database_models import UserModel
from src.user import User


class DatabaseUserRepository:
    """Small persistence adapter for company login accounts."""

    def __init__(self, session_factory=SessionLocal):
        self.session_factory = session_factory

    def save(self, user):
        db = self.session_factory()
        try:
            record = db.query(UserModel).filter_by(email=user.email).one_or_none()
            if record is None:
                record = UserModel(email=user.email)
                db.add(record)

            record.display_name = user.display_name
            record.role = user.role
            record.password_salt = user.password_salt
            record.password_hash = user.password_hash
            db.commit()
            db.refresh(record)
            user.id = record.id
            return user
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def find_by_email(self, email):
        db = self.session_factory()
        try:
            record = db.query(UserModel).filter_by(email=email).one_or_none()
            return self._to_domain(record) if record is not None else None
        finally:
            db.close()

    @staticmethod
    def _to_domain(record):
        return User(
            id=record.id,
            email=record.email,
            display_name=record.display_name,
            role=record.role,
            password_salt=record.password_salt,
            password_hash=record.password_hash,
        )
