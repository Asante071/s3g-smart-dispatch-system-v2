"""Password and signed-session handling for the company-login prototype."""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time

from src.user import User, VALID_ROLES


class AuthService:
    TOKEN_LIFETIME_SECONDS = 60 * 60

    def __init__(self, repository, token_secret=None):
        self.repository = repository
        # A configured secret is used in deployments. The process-local fallback
        # keeps the prototype usable without putting a secret in source control.
        self._token_secret = (token_secret or os.getenv("AUTH_TOKEN_SECRET") or secrets.token_urlsafe(48)).encode("utf-8")

    def create_user(self, email, display_name, role, password):
        email = self._normalise_email(email)
        role = role.upper()
        if role not in VALID_ROLES:
            raise ValueError("Unsupported company role")
        if not password:
            raise ValueError("Password is required")

        salt = secrets.token_bytes(16)
        user = User(
            email=email,
            display_name=display_name.strip(),
            role=role,
            password_salt=self._encode(salt),
            password_hash=self._encode(self._derive_key(password, salt)),
        )
        return self.repository.save(user)

    def ensure_demo_users(self):
        # These are intentionally limited to a local, simulated company login.
        # Passwords are only stored as salted scrypt hashes.
        demo_accounts = (
            ("employee@s3g.local", "Amina Employee", "EMPLOYEE"),
            ("sarah@s3g.local", "Sarah", "TECHNICIAN"),
            ("david@s3g.local", "David", "TECHNICIAN"),
            ("mike@s3g.local", "Mike", "TECHNICIAN"),
            ("supervisor@s3g.local", "Sam Supervisor", "SUPERVISOR"),
        )
        for email, display_name, role in demo_accounts:
            existing_user = self.repository.find_by_email(email)
            if existing_user is None:
                self.create_user(email, display_name, role, "DispatchDemo!2026")
            elif existing_user.display_name != display_name or existing_user.role != role:
                # Demo users are role fixtures for this local prototype.  Keep
                # their existing salted credential, but reconcile a stale role
                # or label so sign-in and backend authorization agree.
                existing_user.display_name = display_name
                existing_user.role = role
                self.repository.save(existing_user)

    def authenticate(self, email, password):
        user = self.repository.find_by_email(self._normalise_email(email))
        if user is None:
            # Run equivalent password work to make account discovery harder.
            self._derive_key(password, b"\0" * 16)
            return None

        calculated = self._derive_key(password, self._decode(user.password_salt))
        if not hmac.compare_digest(calculated, self._decode(user.password_hash)):
            return None
        return user

    def issue_token(self, user):
        issued_at = int(time.time())
        payload = {
            "sub": user.email,
            "role": user.role,
            "iat": issued_at,
            "exp": issued_at + self.TOKEN_LIFETIME_SECONDS,
        }
        encoded_payload = self._encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        signature = hmac.new(self._token_secret, encoded_payload.encode("ascii"), hashlib.sha256).digest()
        return f"{encoded_payload}.{self._encode(signature)}"

    def user_from_token(self, token):
        try:
            encoded_payload, encoded_signature = token.split(".", 1)
            expected_signature = hmac.new(
                self._token_secret, encoded_payload.encode("ascii"), hashlib.sha256
            ).digest()
            if not hmac.compare_digest(expected_signature, self._decode(encoded_signature)):
                return None
            payload = json.loads(self._decode(encoded_payload))
            if not isinstance(payload.get("exp"), int) or payload["exp"] < time.time():
                return None
            user = self.repository.find_by_email(self._normalise_email(payload.get("sub", "")))
            if user is None or user.role != payload.get("role"):
                return None
            return user
        except (AttributeError, UnicodeDecodeError, ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _derive_key(password, salt):
        return hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=64)

    @staticmethod
    def _normalise_email(email):
        return email.strip().casefold()

    @staticmethod
    def _encode(value):
        return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

    @staticmethod
    def _decode(value):
        return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
