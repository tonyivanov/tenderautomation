"""Web schema: users, user_sessions, tender_views, login_attempts

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("username", sa.String(255), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(72), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="analyst"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )

    op.create_table(
        "user_sessions",
        sa.Column("session_id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
    )
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])
    op.create_index("ix_user_sessions_expires_at", "user_sessions", ["expires_at"])

    op.create_table(
        "tender_views",
        sa.Column("tender_id", sa.String(255),
                  sa.ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("tender_id", "user_id"),
    )

    op.create_table(
        "login_attempts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("ip_address", sa.String(45), nullable=False),
        sa.Column("attempt_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("username", sa.String(255), nullable=False),
    )
    op.create_index("ix_login_attempts_ip_at", "login_attempts",
                    ["ip_address", "attempt_at"])


def downgrade() -> None:
    op.drop_table("login_attempts")
    op.drop_table("tender_views")
    op.drop_table("user_sessions")
    op.drop_table("users")
