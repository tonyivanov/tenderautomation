"""Web CLI — user management. Run from project root with PYTHONPATH=src."""
from __future__ import annotations

import sys
from uuid import uuid4

import click

from core.db import SessionLocal
from core.orm.user import UserORM
from web.auth import hash_password


@click.group()
def main() -> None:
    pass


@main.command("add-user")
@click.option("--username", required=True, help="Username (email or short name)")
@click.option("--password", required=True, prompt=True, hide_input=True,
              confirmation_prompt=True, help="Password")
@click.option("--role", default="analyst",
              type=click.Choice(["analyst", "manager", "admin"]),
              show_default=True)
def add_user(username: str, password: str, role: str) -> None:
    """Create a new specialist user."""
    if len(password) < 8:
        click.echo("Error: password must be at least 8 characters.", err=True)
        sys.exit(1)

    db = SessionLocal()
    try:
        existing = db.query(UserORM).filter(UserORM.username == username).first()
        if existing:
            click.echo(f"Error: user '{username}' already exists.", err=True)
            sys.exit(1)

        user = UserORM(
            id=uuid4(),
            username=username,
            password_hash=hash_password(password),
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        click.echo(f"User created: {username} ({role})")
    finally:
        db.close()


if __name__ == "__main__":
    main()
