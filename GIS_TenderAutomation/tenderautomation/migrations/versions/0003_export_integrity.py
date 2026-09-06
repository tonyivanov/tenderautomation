"""Add durable tender procedure inspection metadata.

Revision ID: 0003
Revises: 0002
Create Date: 2026-07-23
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenders",
        sa.Column(
            "procedure_state",
            sa.String(20),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "tenders",
        sa.Column("procedure_checked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenders",
        sa.Column("procedure_last_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenders",
        sa.Column("procedure_source", sa.String(50), nullable=True),
    )
    op.add_column(
        "tenders",
        sa.Column("procedure_error_category", sa.String(50), nullable=True),
    )
    op.create_index(
        "ix_tenders_procedure_state", "tenders", ["procedure_state"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_tenders_procedure_state", table_name="tenders")
    op.drop_column("tenders", "procedure_error_category")
    op.drop_column("tenders", "procedure_source")
    op.drop_column("tenders", "procedure_last_attempt_at")
    op.drop_column("tenders", "procedure_checked_at")
    op.drop_column("tenders", "procedure_state")
