"""create meeting tables

Revision ID: 20260528_01
Revises:
Create Date: 2026-05-28
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260528_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "meetings",
        sa.Column("meeting_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_code", sa.String(length=50), nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_login_id", sa.String(length=50), nullable=False),
        sa.Column("created_by_role", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("max_participants", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.PrimaryKeyConstraint("meeting_id"),
        sa.UniqueConstraint("meeting_code"),
    )
    op.create_index(op.f("ix_meetings_created_by_login_id"), "meetings", ["created_by_login_id"], unique=False)
    op.create_index(op.f("ix_meetings_meeting_code"), "meetings", ["meeting_code"], unique=False)
    op.create_index(op.f("ix_meetings_status"), "meetings", ["status"], unique=False)

    op.create_table(
        "meeting_participants",
        sa.Column("participant_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("login_id", sa.String(length=50), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("connection_id", sa.String(length=80), nullable=True),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_connected", sa.Boolean(), nullable=False),
        sa.Column("audio_muted", sa.Boolean(), nullable=False),
        sa.Column("video_enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.meeting_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("participant_id"),
        sa.UniqueConstraint("meeting_id", "login_id", name="uq_meeting_participant_login"),
    )
    op.create_index(op.f("ix_meeting_participants_connection_id"), "meeting_participants", ["connection_id"], unique=False)
    op.create_index(op.f("ix_meeting_participants_login_id"), "meeting_participants", ["login_id"], unique=False)
    op.create_index(op.f("ix_meeting_participants_meeting_id"), "meeting_participants", ["meeting_id"], unique=False)

    op.create_table(
        "meeting_events",
        sa.Column("event_id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("meeting_id", sa.Integer(), nullable=False),
        sa.Column("actor_login_id", sa.String(length=50), nullable=True),
        sa.Column("actor_role", sa.String(length=20), nullable=True),
        sa.Column("event_type", sa.String(length=50), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.meeting_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("event_id"),
    )
    op.create_index(op.f("ix_meeting_events_actor_login_id"), "meeting_events", ["actor_login_id"], unique=False)
    op.create_index(op.f("ix_meeting_events_event_type"), "meeting_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_meeting_events_meeting_id"), "meeting_events", ["meeting_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_meeting_events_meeting_id"), table_name="meeting_events")
    op.drop_index(op.f("ix_meeting_events_event_type"), table_name="meeting_events")
    op.drop_index(op.f("ix_meeting_events_actor_login_id"), table_name="meeting_events")
    op.drop_table("meeting_events")

    op.drop_index(op.f("ix_meeting_participants_meeting_id"), table_name="meeting_participants")
    op.drop_index(op.f("ix_meeting_participants_login_id"), table_name="meeting_participants")
    op.drop_index(op.f("ix_meeting_participants_connection_id"), table_name="meeting_participants")
    op.drop_table("meeting_participants")

    op.drop_index(op.f("ix_meetings_status"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_meeting_code"), table_name="meetings")
    op.drop_index(op.f("ix_meetings_created_by_login_id"), table_name="meetings")
    op.drop_table("meetings")
