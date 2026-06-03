from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def import_models() -> None:
    from app.modules.meetings.model import Meeting, MeetingEvent, MeetingParticipant  # noqa: F401
