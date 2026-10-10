"""Explicit one-time administrator bootstrap; password is read from protected stdin."""

from __future__ import annotations

import argparse
import getpass
import os

from sqlalchemy.orm import Session, sessionmaker

from app.auth.security import PasswordService
from app.auth.service import AuthError, bootstrap_admin
from app.db.base import make_session_factory


def create_admin(factory: sessionmaker[Session], login: str, password: str) -> str:
    with factory.begin() as db:
        user = bootstrap_admin(db, login, password, PasswordService())
        return user.id


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the first platform administrator")
    parser.add_argument("--login", required=True)
    args = parser.parse_args()
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        parser.error("DATABASE_URL is required")
    password = getpass.getpass("New administrator password (12-128 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation:
        parser.error("passwords do not match")
    try:
        user_id = create_admin(make_session_factory(database_url), args.login, password)
    except (AuthError, ValueError) as exc:
        parser.error(str(exc))
    print(f"Administrator created: {user_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
