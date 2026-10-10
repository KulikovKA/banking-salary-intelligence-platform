"""Password and opaque-token helpers. Never persist or log plaintext tokens."""

from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError


class PasswordService:
    """Argon2id password hashing with explicit RFC 9106 low-memory profile."""

    def __init__(self) -> None:
        self._hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, type=Type.ID)
        self._dummy_hash = self._hasher.hash("constant dummy credential; never accepted")

    @staticmethod
    def validate(password: str) -> None:
        if not 12 <= len(password) <= 128:
            raise ValueError("PASSWORD_POLICY")
        if len(password.encode("utf-8")) > 512:
            raise ValueError("PASSWORD_POLICY")

    def hash(self, password: str) -> str:
        self.validate(password)
        return self._hasher.hash(password)

    def verify(self, encoded: str, password: str) -> bool:
        try:
            return self._hasher.verify(encoded, password)
        except (VerifyMismatchError, VerificationError, InvalidHashError):
            return False

    def needs_rehash(self, encoded: str) -> bool:
        return self._hasher.check_needs_rehash(encoded)

    @property
    def dummy_hash(self) -> str:
        return self._dummy_hash


def new_secret() -> str:
    """Generate a 256-bit, URL-safe secret for a cookie or one-time link."""
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def normalize_login(login: str) -> str:
    return login.strip().casefold()
