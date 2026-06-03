from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base import Base


class Meeting(Base):
    __tablename__ = "meetings"

    meeting_id: Mapped[int] = mapped_column("meeting_id", Integer, primary_key=True, autoincrement=True)
    meeting_code: Mapped[str] = mapped_column("meeting_code", String(50), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column("title", String(150), nullable=False)
    description: Mapped[str | None] = mapped_column("description", Text, nullable=True)
    created_by_login_id: Mapped[str] = mapped_column("created_by_login_id", String(50), nullable=False, index=True)
    created_by_role: Mapped[str] = mapped_column("created_by_role", String(20), nullable=False)
    status: Mapped[str] = mapped_column("status", String(20), nullable=False, default="SCHEDULED", index=True)
    starts_at: Mapped[datetime | None] = mapped_column("starts_at", DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column("ended_at", DateTime(timezone=True), nullable=True)
    max_participants: Mapped[int] = mapped_column("max_participants", Integer, nullable=False, default=8)
    created_at: Mapped[datetime | None] = mapped_column("created_at", DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime | None] = mapped_column(
        "updated_at",
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )


class MeetingParticipant(Base):
    __tablename__ = "meeting_participants"
    __table_args__ = (UniqueConstraint("meeting_id", "login_id", name="uq_meeting_participant_login"),)

    participant_id: Mapped[int] = mapped_column("participant_id", Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        "meeting_id",
        ForeignKey("meetings.meeting_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    login_id: Mapped[str] = mapped_column("login_id", String(50), nullable=False, index=True)
    role: Mapped[str] = mapped_column("role", String(20), nullable=False)
    display_name: Mapped[str | None] = mapped_column("display_name", String(100), nullable=True)
    connection_id: Mapped[str | None] = mapped_column("connection_id", String(80), nullable=True, index=True)
    joined_at: Mapped[datetime | None] = mapped_column("joined_at", DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column("last_seen_at", DateTime(timezone=True), nullable=True)
    left_at: Mapped[datetime | None] = mapped_column("left_at", DateTime(timezone=True), nullable=True)
    is_connected: Mapped[bool] = mapped_column("is_connected", Boolean, nullable=False, default=True)
    audio_muted: Mapped[bool] = mapped_column("audio_muted", Boolean, nullable=False, default=False)
    video_enabled: Mapped[bool] = mapped_column("video_enabled", Boolean, nullable=False, default=True)


class MeetingEvent(Base):
    __tablename__ = "meeting_events"

    event_id: Mapped[int] = mapped_column("event_id", Integer, primary_key=True, autoincrement=True)
    meeting_id: Mapped[int] = mapped_column(
        "meeting_id",
        ForeignKey("meetings.meeting_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    actor_login_id: Mapped[str | None] = mapped_column("actor_login_id", String(50), nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column("actor_role", String(20), nullable=True)
    event_type: Mapped[str] = mapped_column("event_type", String(50), nullable=False, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column("payload", JSON, nullable=True)
    created_at: Mapped[datetime | None] = mapped_column("created_at", DateTime(timezone=True), server_default=func.now())
