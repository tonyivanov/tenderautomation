"""Notifications CLI. Run: python -m notifications.cli send-digest"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

import click

from core.config import settings
from core.repositories import TenderRepository
from notifications.email_digest import EmailDigest


def _build_email_digest() -> EmailDigest:
    return EmailDigest(
        smtp_host=settings.smtp_host,
        smtp_port=settings.smtp_port,
        smtp_username=settings.smtp_username,
        smtp_password=settings.smtp_password,
        smtp_from=settings.smtp_from,
        recipients=settings.get_email_recipients(),
    )


@click.group()
def main() -> None:
    pass


@main.command("send-digest")
@click.option("--hours", default=24, show_default=True,
              help="Period in hours to look back for new tenders")
def send_digest(hours: int) -> None:
    """Send daily email digest of new qualified tenders."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    repo = TenderRepository()
    tenders = repo.get_qualified(since=since)

    date_str = datetime.now(timezone.utc).strftime("%d.%m.%Y")
    digest = _build_email_digest()
    message = digest.build_digest(tenders, date_str)

    click.echo(f"Sending digest: {len(tenders)} tenders to {len(message.recipients)} recipients")
    try:
        digest.send(message)
        click.echo("Done.")
    except Exception as e:
        click.echo(f"Failed: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
