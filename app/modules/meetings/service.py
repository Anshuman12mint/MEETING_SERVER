from __future__ import annotations

from datetime import datetime, timedelta, timezone
import secrets

from fastapi import HTTPException, status

from app.common import helpers, validators
from app.core.config import get_settings, utc_now
from app.modules.auth.schemas import AuthenticatedPrincipal
from app.modules.meetings.model import Meeting, MeetingEvent, MeetingParticipant
from app.modules.meetings.repository import MeetingEventRepository, MeetingParticipantRepository, MeetingRepository
from app.modules.meetings.schemas import (
    IceServerRead,
    MeetingCreateRequest,
    MeetingEndRequest,
    MeetingJoinRequest,
    MeetingJoinResponse,
    MeetingParticipantRead,
    MeetingRead,
)


MEETING_STATUSES = {"SCHEDULED", "ACTIVE", "ENDED"}
CREATOR_ROLES = {"ADMIN", "TEACHER"}


class MeetingService:
    def __init__(
        self,
        meeting_repository: MeetingRepository,
        participant_repository: MeetingParticipantRepository,
        event_repository: MeetingEventRepository,
    ) -> None:
        self.meeting_repository = meeting_repository
        self.participant_repository = participant_repository
        self.event_repository = event_repository
        self.settings = get_settings()

    def get_meetings(self, status_filter: str | None = None, search: str | None = None) -> list[MeetingRead]:
        self.cleanup_idle_meetings()
        meetings = [self.to_read(meeting) for meeting in self.meeting_repository.find_all_ordered()]
        if validators.has_text(status_filter):
            normalized_status = self.normalize_status(status_filter)
            meetings = [meeting for meeting in meetings if meeting.status == normalized_status]
        if validators.has_text(search):
            query = search.strip().lower()
            meetings = [
                meeting
                for meeting in meetings
                if query
                in " ".join(
                    [
                        meeting.meeting_code or "",
                        meeting.title or "",
                        meeting.description or "",
                        meeting.created_by_login_id or "",
                        meeting.status or "",
                    ]
                ).lower()
            ]
        return meetings

    def get_meeting(self, meeting_id: int) -> MeetingRead:
        self.cleanup_idle_meetings()
        return self.to_read(self.find_meeting(meeting_id))

    def create_meeting(self, request: MeetingCreateRequest, principal: AuthenticatedPrincipal) -> MeetingRead:
        self.ensure_can_create(principal)
        validators.require_text(request.title, "title")
        max_participants = request.max_participants or self.settings.max_participants_per_meeting
        validators.require(max_participants > 0, "maxParticipants must be greater than zero")

        starts_at = self.normalize_datetime(request.starts_at) or utc_now()
        now = utc_now()
        meeting_code = helpers.normalize_code(request.meeting_code) or self.generate_meeting_code()
        if self.meeting_repository.exists_by_code(meeting_code):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="meetingCode already exists")

        meeting = Meeting()
        meeting.meeting_code = meeting_code
        meeting.title = helpers.trim_to_none(request.title) or ""
        meeting.description = helpers.trim_to_none(request.description)
        meeting.created_by_login_id = principal.login_id
        meeting.created_by_role = principal.role
        meeting.status = "SCHEDULED" if starts_at > now else "ACTIVE"
        meeting.starts_at = starts_at
        meeting.max_participants = max_participants
        self.meeting_repository.save(meeting)
        self.record_event(meeting, principal, "meeting_created", {"status": meeting.status})
        return self.to_read(meeting)

    def join_meeting(
        self,
        meeting_id: int,
        request: MeetingJoinRequest,
        principal: AuthenticatedPrincipal,
        ws_url: str,
    ) -> MeetingJoinResponse:
        self.cleanup_idle_meetings()
        meeting = self.find_meeting(meeting_id)
        if meeting.status == "ENDED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meeting has ended")

        now = utc_now()
        if meeting.status != "ACTIVE":
            meeting.status = "ACTIVE"
            if meeting.starts_at is None:
                meeting.starts_at = now
            self.meeting_repository.save(meeting)

        existing_participant = self.participant_repository.find_by_meeting_and_login_id(meeting.meeting_id, principal.login_id)
        participant = existing_participant or MeetingParticipant()
        participant.meeting_id = meeting.meeting_id
        participant.login_id = principal.login_id
        participant.role = principal.role
        participant.display_name = helpers.trim_to_none(request.display_name) or principal.login_id
        participant.connection_id = None
        participant.last_seen_at = now
        participant.left_at = None
        participant.is_connected = False
        participant.audio_muted = False
        participant.video_enabled = True
        self.participant_repository.save(participant)

        event_type = "participant_join_requested" if existing_participant is None else "participant_rejoin_requested"
        self.record_event(
            meeting,
            principal,
            event_type,
            {"participantId": participant.participant_id},
        )
        return MeetingJoinResponse(
            meeting=self.to_read(meeting),
            participant=self.to_participant_read(participant),
            ws_url=ws_url,
            ice_servers=[IceServerRead(urls=url) for url in self.settings.ice_server_urls],
        )

    def open_signaling_connection(
        self,
        meeting_id: int,
        principal: AuthenticatedPrincipal,
        display_name: str | None = None,
    ) -> MeetingParticipantRead:
        self.cleanup_idle_meetings()
        meeting = self.find_meeting(meeting_id)
        if meeting.status == "ENDED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meeting has ended")

        existing_participant = self.participant_repository.find_by_meeting_and_login_id(meeting.meeting_id, principal.login_id)
        connected_participants = self.participant_repository.find_connected_by_meeting_id(meeting.meeting_id)
        is_new_connection = existing_participant is None or not existing_participant.is_connected
        if is_new_connection and len(connected_participants) >= meeting.max_participants:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Meeting is full")

        now = utc_now()
        if meeting.status != "ACTIVE":
            meeting.status = "ACTIVE"
            if meeting.starts_at is None:
                meeting.starts_at = now
            self.meeting_repository.save(meeting)

        participant = existing_participant or MeetingParticipant()
        participant.meeting_id = meeting.meeting_id
        participant.login_id = principal.login_id
        participant.role = principal.role
        participant.display_name = helpers.trim_to_none(display_name) or participant.display_name or principal.login_id
        participant.connection_id = secrets.token_urlsafe(18)
        participant.last_seen_at = now
        participant.left_at = None
        participant.is_connected = True
        participant.audio_muted = False
        participant.video_enabled = True
        self.participant_repository.save(participant)

        event_type = "participant_reconnected" if existing_participant is not None else "participant_connected"
        self.record_event(
            meeting,
            principal,
            event_type,
            {"participantId": participant.participant_id, "connectionId": participant.connection_id},
        )
        return self.to_participant_read(participant)

    def close_signaling_connection(self, meeting_id: int, login_id: str, connection_id: str) -> bool:
        meeting = self.meeting_repository.find_by_id(meeting_id)
        if meeting is None:
            return False
        participant = self.participant_repository.find_by_meeting_and_login_id(meeting_id, login_id)
        if participant is None or participant.connection_id != connection_id:
            return False

        now = utc_now()
        participant.is_connected = False
        participant.left_at = now
        participant.last_seen_at = now
        self.participant_repository.save(participant)
        self.record_event(
            meeting,
            AuthenticatedPrincipal(login_id=login_id, role=participant.role),
            "participant_disconnected",
            {"participantId": participant.participant_id, "connectionId": connection_id},
        )
        return True

    def cleanup_idle_meetings(self) -> list[MeetingRead]:
        now = utc_now()
        cutoff = now - timedelta(seconds=self.settings.meeting_idle_timeout_seconds)
        system_principal = AuthenticatedPrincipal(login_id="SYSTEM", role="System")
        ended_meetings: list[MeetingRead] = []
        for meeting in self.meeting_repository.find_by_status_ordered("ACTIVE"):
            if self.participant_repository.find_connected_by_meeting_id(meeting.meeting_id):
                continue
            latest_activity_at = self.latest_meeting_activity_at(meeting)
            if latest_activity_at > cutoff:
                continue
            meeting.status = "ENDED"
            meeting.ended_at = now
            self.meeting_repository.save(meeting)
            self.record_event(
                meeting,
                system_principal,
                "meeting_auto_ended",
                {"reason": "idle_timeout", "idleTimeoutSeconds": self.settings.meeting_idle_timeout_seconds},
            )
            ended_meetings.append(self.to_read(meeting))
        return ended_meetings

    def end_meeting(
        self,
        meeting_id: int,
        request: MeetingEndRequest,
        principal: AuthenticatedPrincipal,
    ) -> MeetingRead:
        meeting = self.find_meeting(meeting_id)
        self.ensure_can_end(meeting, principal)
        if meeting.status == "ENDED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Meeting has already ended")

        now = utc_now()
        meeting.status = "ENDED"
        meeting.ended_at = now
        self.meeting_repository.save(meeting)
        for participant in self.participant_repository.find_connected_by_meeting_id(meeting.meeting_id):
            participant.is_connected = False
            participant.left_at = now
            participant.last_seen_at = now
            self.participant_repository.save(participant)
        self.record_event(meeting, principal, "meeting_ended", {"reason": helpers.trim_to_none(request.reason)})
        return self.to_read(meeting)

    def find_meeting(self, meeting_id: int | None) -> Meeting:
        meeting = self.meeting_repository.find_by_id(meeting_id)
        if meeting is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")
        return meeting

    def latest_meeting_activity_at(self, meeting: Meeting) -> datetime:
        candidates = [meeting.updated_at, meeting.starts_at, meeting.created_at]
        for participant in self.participant_repository.find_by_meeting_id(meeting.meeting_id):
            candidates.extend([participant.last_seen_at, participant.left_at, participant.joined_at])
        normalized = [self.normalize_datetime(candidate) for candidate in candidates if candidate is not None]
        return max(normalized) if normalized else utc_now()

    def generate_meeting_code(self) -> str:
        while True:
            candidate = "MTG-" + secrets.token_hex(4).upper()
            if not self.meeting_repository.exists_by_code(candidate):
                return candidate

    def record_event(
        self,
        meeting: Meeting,
        principal: AuthenticatedPrincipal,
        event_type: str,
        payload: dict[str, object] | None = None,
    ) -> MeetingEvent:
        event = MeetingEvent()
        event.meeting_id = meeting.meeting_id
        event.actor_login_id = principal.login_id
        event.actor_role = principal.role
        event.event_type = event_type
        event.payload = payload
        return self.event_repository.save(event)

    def ensure_can_create(self, principal: AuthenticatedPrincipal) -> None:
        if principal.role.strip().upper() not in CREATOR_ROLES:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers and admins can create meetings")

    def ensure_can_end(self, meeting: Meeting, principal: AuthenticatedPrincipal) -> None:
        normalized_role = principal.role.strip().upper()
        if normalized_role == "ADMIN":
            return
        if normalized_role == "TEACHER" and meeting.created_by_login_id.lower() == principal.login_id.lower():
            return
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the meeting creator or an admin can end this meeting")

    def normalize_status(self, value: str | None) -> str:
        validators.require_text(value, "status")
        assert value is not None
        normalized = value.strip().upper()
        if normalized not in MEETING_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status must be one of: ACTIVE, ENDED, SCHEDULED")
        return normalized

    def normalize_datetime(self, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def to_read(self, meeting: Meeting) -> MeetingRead:
        return MeetingRead(
            meeting_id=meeting.meeting_id,
            meeting_code=meeting.meeting_code,
            title=meeting.title,
            description=meeting.description,
            created_by_login_id=meeting.created_by_login_id,
            created_by_role=meeting.created_by_role,
            status=meeting.status,
            starts_at=meeting.starts_at,
            ended_at=meeting.ended_at,
            max_participants=meeting.max_participants,
            created_at=meeting.created_at,
            updated_at=meeting.updated_at,
        )

    def to_participant_read(self, participant: MeetingParticipant) -> MeetingParticipantRead:
        return MeetingParticipantRead(
            participant_id=participant.participant_id,
            meeting_id=participant.meeting_id,
            login_id=participant.login_id,
            role=participant.role,
            display_name=participant.display_name,
            connection_id=participant.connection_id,
            joined_at=participant.joined_at,
            last_seen_at=participant.last_seen_at,
            left_at=participant.left_at,
            is_connected=participant.is_connected,
            audio_muted=participant.audio_muted,
            video_enabled=participant.video_enabled,
        )
