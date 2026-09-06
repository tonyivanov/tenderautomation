"""Initial schema: tenders, tender_actions, collection_runs

Revision ID: 0001
Revises:
Create Date: 2026-06-04
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenders",
        sa.Column("id", sa.String(255), primary_key=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("buyer", sa.Text, nullable=True),
        sa.Column("budget", sa.Numeric(18, 2), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("raw_data", postgresql.JSON, nullable=False, server_default="{}"),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("prefilter_score", sa.Integer, nullable=False, server_default="0"),
        sa.Column("qualification_tier", sa.String(20), nullable=True),
        sa.Column("matched_keywords", postgresql.JSON, nullable=False, server_default="[]"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("collected_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_tenders_platform_status", "tenders", ["platform", "status"])
    op.create_index("ix_tenders_collected_at", "tenders", ["collected_at"])

    op.create_table(
        "tender_actions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("tender_id", sa.String(255),
                  sa.ForeignKey("tenders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(20), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("ai_tier", sa.String(10), nullable=True),
        sa.Column("ai_rationale", sa.Text, nullable=True),
        sa.Column("ai_tool", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("NOW()")),
    )
    op.create_index("ix_tender_actions_tender_id", "tender_actions", ["tender_id"])

    op.create_table(
        "collection_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("new_tenders_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated_tenders_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("attempt_number", sa.Integer, nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_collection_runs_platform_status",
        "collection_runs", ["platform", "status", "completed_at"]
    )


def downgrade() -> None:
    op.drop_table("collection_runs")
    op.drop_table("tender_actions")
    op.drop_table("tenders")
