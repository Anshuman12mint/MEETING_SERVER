from __future__ import annotations

import unittest

from app.modules.auth.schemas import AuthenticatedPrincipal
from app.modules.meetings.signaling import SignalingManager


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.closed = False
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self.sent_json: list[dict[str, object]] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict[str, object]) -> None:
        self.sent_json.append(payload)

    async def close(self, code: int = 1000, reason: str | None = None) -> None:
        self.closed = True
        self.close_code = code
        self.close_reason = reason


class SignalingManagerTests(unittest.IsolatedAsyncioTestCase):
    async def test_connect_relay_and_disconnect_flow(self) -> None:
        manager = SignalingManager()
        teacher = AuthenticatedPrincipal(login_id="TCH-00001", role="Teacher")
        student = AuthenticatedPrincipal(login_id="STU-00001", role="Student")
        teacher_socket = FakeWebSocket()
        student_socket = FakeWebSocket()

        teacher_connection = await manager.connect(1, teacher_socket, teacher, display_name="Teacher One")
        student_connection = await manager.connect(1, student_socket, student, display_name="Asha")

        self.assertTrue(teacher_socket.accepted)
        self.assertTrue(student_socket.accepted)
        self.assertEqual(manager.room_size(1), 2)
        self.assertEqual(teacher_socket.sent_json[0]["type"], "participants_snapshot")
        self.assertEqual(teacher_socket.sent_json[1]["type"], "participant_joined")
        self.assertEqual(student_socket.sent_json[0]["type"], "participants_snapshot")
        self.assertEqual(student_socket.sent_json[0]["participants"][0]["loginId"], "TCH-00001")

        await manager.handle_client_message(
            1,
            teacher_connection.connection_id,
            {"type": "offer", "to": "STU-00001", "payload": {"sdp": "fake-offer"}},
        )

        relay = student_socket.sent_json[-1]
        self.assertEqual(relay["type"], "offer")
        self.assertEqual(relay["from"], "TCH-00001")
        self.assertEqual(relay["fromLoginId"], "TCH-00001")
        self.assertEqual(relay["fromConnectionId"], teacher_connection.connection_id)
        self.assertEqual(relay["to"], "STU-00001")
        self.assertEqual(relay["toLoginId"], "STU-00001")
        self.assertEqual(relay["payload"], {"sdp": "fake-offer"})

        await manager.handle_client_message(
            1,
            student_connection.connection_id,
            {"type": "iceCandidate", "toConnectionId": teacher_connection.connection_id, "payload": {"candidate": "fake"}},
        )
        relay_by_connection = teacher_socket.sent_json[-1]
        self.assertEqual(relay_by_connection["type"], "ice_candidate")
        self.assertEqual(relay_by_connection["toConnectionId"], teacher_connection.connection_id)

        await manager.handle_client_message(1, teacher_connection.connection_id, {"type": "ping"})
        self.assertEqual(teacher_socket.sent_json[-1]["type"], "pong")

        await manager.handle_client_message(1, teacher_connection.connection_id, {"type": "join"})
        self.assertEqual(teacher_socket.sent_json[-1]["type"], "participants_snapshot")

        await manager.disconnect(1, student.login_id, student_connection.connection_id)
        self.assertEqual(manager.room_size(1), 1)
        self.assertEqual(teacher_socket.sent_json[-1]["type"], "participant_left")

        await manager.disconnect(1, teacher.login_id, teacher_connection.connection_id)
        self.assertEqual(manager.room_size(1), 0)

    async def test_invalid_or_missing_target_messages_return_errors(self) -> None:
        manager = SignalingManager()
        teacher = AuthenticatedPrincipal(login_id="TCH-00001", role="Teacher")
        socket = FakeWebSocket()
        connection = await manager.connect(1, socket, teacher)

        await manager.handle_client_message(1, connection.connection_id, {"type": "offer", "payload": {}})
        self.assertEqual(socket.sent_json[-1]["type"], "error")
        self.assertEqual(socket.sent_json[-1]["code"], "target_required")

        await manager.handle_client_message(1, connection.connection_id, {"type": "something_else", "payload": {}})
        self.assertEqual(socket.sent_json[-1]["type"], "error")
        self.assertEqual(socket.sent_json[-1]["code"], "unsupported_message_type")

    async def test_duplicate_login_replaces_existing_connection(self) -> None:
        manager = SignalingManager()
        teacher = AuthenticatedPrincipal(login_id="TCH-00001", role="Teacher")
        first_socket = FakeWebSocket()
        second_socket = FakeWebSocket()

        first_connection = await manager.connect(1, first_socket, teacher)
        second_connection = await manager.connect(1, second_socket, teacher)

        self.assertTrue(first_socket.closed)
        self.assertEqual(first_socket.close_code, 4000)
        self.assertEqual(manager.room_size(1), 1)
        self.assertNotEqual(first_connection.connection_id, second_connection.connection_id)


if __name__ == "__main__":
    unittest.main()
