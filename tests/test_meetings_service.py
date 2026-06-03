from __future__ import annotations

from datetime import timedelta
import os
import unittest

from fastapi import HTTPException

from app.core.config import clear_settings_cache, utc_now
from app.db.session import initialize_database, reset_database_state, session_context
from app.modules.auth.schemas import AuthenticatedPrincipal
from app.modules.meetings.repository import MeetingEventRepository, MeetingParticipantRepository, MeetingRepository
from app.modules.meetings.router import get_ice_config
from app.modules.meetings.schemas import MeetingCreateRequest, MeetingEndRequest, MeetingJoinRequest
from app.modules.meetings.service import MeetingService


class MeetingServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.original_env = os.environ.copy()
        os.environ.update(
            {
                "APP_ENV": "test",
                "DB_URL": "sqlite+pysqlite:///:memory:",
                "JWT_SECRET": "meeting-test-secret-value",
                "ICE_SERVERS": "stun:stun.l.google.com:19302,stun:stun1.l.google.com:19302",
                "MEETING_IDLE_TIMEOUT_SECONDS": "60",
                "MAX_PARTICIPANTS_PER_MEETING": "2",
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

    def test_teacher_can_create_student_can_join_and_creator_can_end(self) -> None:
        with session_context() as session:
            service = self.build_service(session)
            teacher = AuthenticatedPrincipal(login_id="TCH-00001", role="Teacher")
            student = AuthenticatedPrincipal(login_id="STU-00001", role="Student")

            meeting = service.create_meeting(
                MeetingCreateRequest(title="Programming Class", meeting_code="bca-live", max_participants=2),
                teacher,
            )

            self.assertEqual(meeting.meeting_code, "BCA-LIVE")
            self.assertEqual(meeting.status, "ACTIVE")
            self.assertEqual(len(service.get_meetings(status_filter="active")), 1)

            join = service.join_meeting(
                meeting.meeting_id,
                MeetingJoinRequest(display_name="Asha"),
                student,
                "ws://127.0.0.1:8001/ws/meetings/1?token=test",
            )

            self.assertEqual(join.participant.login_id, "STU-00001")
            self.assertEqual(join.participant.display_name, "Asha")
            self.assertFalse(join.participant.is_connected)
            self.assertIsNone(join.participant.connection_id)
            self.assertEqual(len(join.ice_servers), 2)
            self.assertTrue(join.ws_url.startswith("ws://127.0.0.1:8001/ws/meetings/1"))

            ended = service.end_meeting(meeting.meeting_id, MeetingEndRequest(reason="Class finished"), teacher)
            self.assertEqual(ended.status, "ENDED")

            with self.assertRaises(HTTPException) as join_after_end:
                service.join_meeting(
                    meeting.meeting_id,
                    MeetingJoinRequest(),
                    student,
                    "ws://127.0.0.1:8001/ws/meetings/1?token=test",
                )
            self.assertEqual(join_after_end.exception.status_code, 400)

    def test_students_cannot_create_and_other_teachers_cannot_end(self) -> None:
        with session_context() as session:
            service = self.build_service(session)
            teacher = AuthenticatedPrincipal(login_id="TCH-00001", role="Teacher")
            other_teacher = AuthenticatedPrincipal(login_id="TCH-00002", role="Teacher")
            student = AuthenticatedPrincipal(login_id="STU-00001", role="Student")

            with self.assertRaises(HTTPException) as create_denied:
                service.create_meeting(MeetingCreateRequest(title="Student Room"), student)
            self.assertEqual(create_denied.exception.status_code, 403)

            meeting = service.create_meeting(MeetingCreateRequest(title="Teacher Room"), teacher)
            with self.assertRaises(HTTPException) as end_denied:
                service.end_meeting(meeting.meeting_id, MeetingEndRequest(), other_teacher)
            self.assertEqual(end_denied.exception.status_code, 403)

    def test_signaling_connection_updates_database_and_ignores_stale_disconnect(self) -> None:
        with session_context() as session:
            service = self.build_service(session)
            participants = MeetingParticipantRepository(session)
            teacher = AuthenticatedPrincipal(login_id="TCH-00001", role="Teacher")
            student = AuthenticatedPrincipal(login_id="STU-00001", role="Student")

            meeting = service.create_meeting(MeetingCreateRequest(title="Live Class"), teacher)
            service.join_meeting(
                meeting.meeting_id,
                MeetingJoinRequest(display_name="Asha"),
                student,
                "ws://127.0.0.1:8001/ws/meetings/1?token=test",
            )

            first_connection = service.open_signaling_connection(meeting.meeting_id, student)
            self.assertTrue(first_connection.is_connected)
            self.assertEqual(first_connection.display_name, "Asha")
            self.assertIsNotNone(first_connection.connection_id)

            second_connection = service.open_signaling_connection(meeting.meeting_id, student, display_name="Asha Rawat")
            self.assertTrue(second_connection.is_connected)
            self.assertNotEqual(first_connection.connection_id, second_connection.connection_id)

            self.assertFalse(service.close_signaling_connection(meeting.meeting_id, student.login_id, first_connection.connection_id or ""))
            current = participants.find_by_meeting_and_login_id(meeting.meeting_id, student.login_id)
            self.assertIsNotNone(current)
            self.assertTrue(current.is_connected)
            self.assertEqual(current.display_name, "Asha Rawat")

            self.assertTrue(service.close_signaling_connection(meeting.meeting_id, student.login_id, second_connection.connection_id or ""))
            self.assertFalse(current.is_connected)
            self.assertIsNotNone(current.left_at)

    def test_idle_meetings_auto_end_after_timeout(self) -> None:
        with session_context() as session:
            service = self.build_service(session)
            meetings = MeetingRepository(session)
            teacher = AuthenticatedPrincipal(login_id="TCH-00001", role="Teacher")

            meeting = service.create_meeting(MeetingCreateRequest(title="Empty Old Class"), teacher)
            meeting_model = meetings.find_by_id(meeting.meeting_id)
            self.assertIsNotNone(meeting_model)
            assert meeting_model is not None
            old_time = utc_now() - timedelta(seconds=120)
            meeting_model.starts_at = old_time
            meeting_model.created_at = old_time
            meeting_model.updated_at = old_time
            meetings.save(meeting_model)

            ended = service.cleanup_idle_meetings()

            self.assertEqual(len(ended), 1)
            self.assertEqual(ended[0].status, "ENDED")

    def test_ice_config_exposes_frontend_protocol_contract(self) -> None:
        config = get_ice_config(AuthenticatedPrincipal(login_id="TCH-00001", role="Teacher"))

        self.assertEqual([server.urls for server in config.ice_servers], ["stun:stun.l.google.com:19302", "stun:stun1.l.google.com:19302"])
        self.assertIn("offer", config.signaling.client_message_types)
        self.assertIn("ice_candidate", config.signaling.client_message_types)
        self.assertIn("participants_snapshot", config.signaling.server_message_types)
        self.assertIn("offer", config.signaling.target_required_types)
        self.assertIn("toConnectionId", config.signaling.target_fields)

    def build_service(self, session) -> MeetingService:
        return MeetingService(
            MeetingRepository(session),
            MeetingParticipantRepository(session),
            MeetingEventRepository(session),
        )


if __name__ == "__main__":
    unittest.main()
