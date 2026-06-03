from __future__ import annotations

import os
import unittest

from app.core.config import clear_settings_cache, utc_now
from app.db.session import initialize_database, reset_database_state, session_context
from app.modules.meetings.model import Meeting, MeetingEvent, MeetingParticipant
from app.modules.meetings.repository import MeetingEventRepository, MeetingParticipantRepository, MeetingRepository


class MeetingDatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_env = os.environ.copy()
        os.environ.update(
            {
                "APP_ENV": "test",
                "DB_URL": "sqlite+pysqlite:///:memory:",
                "JWT_SECRET": "meeting-test-secret-value",
            }
        )
        clear_settings_cache()
        reset_database_state()
        initialize_database()

    def tearDown(self) -> None:
        reset_database_state()
        clear_settings_cache()
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_meeting_repositories_persist_core_records(self) -> None:
        with session_context() as session:
            meetings = MeetingRepository(session)
            participants = MeetingParticipantRepository(session)
            events = MeetingEventRepository(session)

            meeting = meetings.save(
                Meeting(
                    meeting_code="M-TEST-001",
                    title="BCA Programming Class",
                    created_by_login_id="TCH-00001",
                    created_by_role="Teacher",
                    status="ACTIVE",
                    starts_at=utc_now(),
                    max_participants=8,
                )
            )
            participant = participants.save(
                MeetingParticipant(
                    meeting_id=meeting.meeting_id,
                    login_id="STU-00001",
                    role="Student",
                    display_name="STU-00001",
                    connection_id="conn-1",
                )
            )
            event = events.save(
                MeetingEvent(
                    meeting_id=meeting.meeting_id,
                    actor_login_id="STU-00001",
                    actor_role="Student",
                    event_type="participant_joined",
                    payload={"connectionId": "conn-1"},
                )
            )

            self.assertEqual(meetings.count(), 1)
            self.assertEqual(meetings.find_by_code("m-test-001").meeting_id, meeting.meeting_id)
            self.assertEqual(participants.find_by_meeting_and_login_id(meeting.meeting_id, "stu-00001").participant_id, participant.participant_id)
            self.assertEqual(len(participants.find_connected_by_meeting_id(meeting.meeting_id)), 1)
            self.assertEqual(events.find_by_meeting_id(meeting.meeting_id)[0].event_id, event.event_id)


if __name__ == "__main__":
    unittest.main()
