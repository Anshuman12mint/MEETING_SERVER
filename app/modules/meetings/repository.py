from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.meetings.model import Meeting, MeetingEvent, MeetingParticipant


class MeetingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, meeting_id: int | None) -> Meeting | None:
        return None if meeting_id is None else self.session.get(Meeting, meeting_id)

    def find_by_code(self, meeting_code: str | None) -> Meeting | None:
        if meeting_code is None:
            return None
        return self.session.scalar(select(Meeting).where(func.lower(Meeting.meeting_code) == meeting_code.strip().lower()))

    def find_all_ordered(self) -> list[Meeting]:
        return list(self.session.scalars(select(Meeting).order_by(Meeting.created_at.desc())))

    def find_by_status_ordered(self, status: str) -> list[Meeting]:
        return list(
            self.session.scalars(
                select(Meeting).where(Meeting.status == status).order_by(Meeting.updated_at.asc())
            )
        )

    def exists_by_code(self, meeting_code: str | None, exclude_meeting_id: int | None = None) -> bool:
        if meeting_code is None:
            return False
        statement = select(func.count()).select_from(Meeting).where(func.lower(Meeting.meeting_code) == meeting_code.strip().lower())
        if exclude_meeting_id is not None:
            statement = statement.where(Meeting.meeting_id != exclude_meeting_id)
        return bool(self.session.scalar(statement))

    def save(self, meeting: Meeting) -> Meeting:
        self.session.add(meeting)
        self.session.flush()
        self.session.refresh(meeting)
        return meeting

    def delete(self, meeting: Meeting) -> None:
        self.session.delete(meeting)
        self.session.flush()

    def count(self) -> int:
        return int(self.session.scalar(select(func.count()).select_from(Meeting)) or 0)


class MeetingParticipantRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_id(self, participant_id: int | None) -> MeetingParticipant | None:
        return None if participant_id is None else self.session.get(MeetingParticipant, participant_id)

    def find_by_meeting_and_login_id(self, meeting_id: int | None, login_id: str | None) -> MeetingParticipant | None:
        if meeting_id is None or login_id is None:
            return None
        return self.session.scalar(
            select(MeetingParticipant).where(
                MeetingParticipant.meeting_id == meeting_id,
                func.lower(MeetingParticipant.login_id) == login_id.strip().lower(),
            )
        )

    def find_connected_by_meeting_id(self, meeting_id: int) -> list[MeetingParticipant]:
        return list(
            self.session.scalars(
                select(MeetingParticipant)
                .where(MeetingParticipant.meeting_id == meeting_id, MeetingParticipant.is_connected.is_(True))
                .order_by(MeetingParticipant.joined_at.asc())
            )
        )

    def find_by_meeting_id(self, meeting_id: int) -> list[MeetingParticipant]:
        return list(
            self.session.scalars(
                select(MeetingParticipant).where(MeetingParticipant.meeting_id == meeting_id).order_by(MeetingParticipant.joined_at.asc())
            )
        )

    def save(self, participant: MeetingParticipant) -> MeetingParticipant:
        self.session.add(participant)
        self.session.flush()
        self.session.refresh(participant)
        return participant

    def delete(self, participant: MeetingParticipant) -> None:
        self.session.delete(participant)
        self.session.flush()


class MeetingEventRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_meeting_id(self, meeting_id: int) -> list[MeetingEvent]:
        return list(
            self.session.scalars(
                select(MeetingEvent).where(MeetingEvent.meeting_id == meeting_id).order_by(MeetingEvent.created_at.asc())
            )
        )

    def save(self, event: MeetingEvent) -> MeetingEvent:
        self.session.add(event)
        self.session.flush()
        self.session.refresh(event)
        return event
