from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import uuid4

from starlette.websockets import WebSocket

from app.common import helpers
from app.modules.auth.schemas import AuthenticatedPrincipal


CONTROL_MESSAGE_TYPES = {"join", "ping"}
RELAY_MESSAGE_TYPES = {"offer", "answer", "ice_candidate", "mute_state", "camera_state"}
TARGET_REQUIRED_MESSAGE_TYPES = {"offer", "answer", "ice_candidate"}
CLIENT_MESSAGE_TYPES = CONTROL_MESSAGE_TYPES | RELAY_MESSAGE_TYPES
SERVER_MESSAGE_TYPES = {
    "participants_snapshot",
    "participant_joined",
    "participant_left",
    "offer",
    "answer",
    "ice_candidate",
    "mute_state",
    "camera_state",
    "pong",
    "error",
}
MESSAGE_TYPE_ALIASES = {
    "icecandidate": "ice_candidate",
    "ice-candidate": "ice_candidate",
    "muteState": "mute_state",
    "mutestate": "mute_state",
    "mute-state": "mute_state",
    "cameraState": "camera_state",
    "camerastate": "camera_state",
    "camera-state": "camera_state",
}



@dataclass
class SignalingConnection:
    meeting_id: int
    connection_id: str
    login_id: str
    role: str
    display_name: str
    websocket: WebSocket

    def to_participant_payload(self) -> dict[str, object]:
        return {
            "connectionId": self.connection_id,
            "loginId": self.login_id,
            "role": self.role,
            "displayName": self.display_name,
        }


class SignalingManager:
    def __init__(self) -> None:
        self.rooms: dict[int, dict[str, SignalingConnection]] = {}

    async def connect(
        self,
        meeting_id: int,
        websocket: WebSocket,
        principal: AuthenticatedPrincipal,
        display_name: str | None = None,
        connection_id: str | None = None,
    ) -> SignalingConnection:
        await websocket.accept()
        room = self.rooms.setdefault(meeting_id, {})
        existing = room.get(principal.login_id)
        if existing is not None:
            await self.safe_close(existing.websocket, code=4000, reason="Replaced by a new connection")

        connection = SignalingConnection(
            meeting_id=meeting_id,
            connection_id=connection_id or uuid4().hex,
            login_id=principal.login_id,
            role=principal.role,
            display_name=helpers.trim_to_none(display_name) or principal.login_id,
            websocket=websocket,
        )
        room[principal.login_id] = connection

        await self.send_snapshot(connection)
        await self.broadcast(
            meeting_id,
            {
                "type": "participant_joined",
                "meetingId": meeting_id,
                "participant": connection.to_participant_payload(),
            },
            exclude_connection_id=connection.connection_id,
        )
        return connection

    async def disconnect(self, meeting_id: int, login_id: str, connection_id: str) -> None:
        room = self.rooms.get(meeting_id)
        if room is None:
            return
        current = room.get(login_id)
        if current is None or current.connection_id != connection_id:
            return

        room.pop(login_id, None)
        if room:
            await self.broadcast(
                meeting_id,
                {
                    "type": "participant_left",
                    "meetingId": meeting_id,
                    "participant": current.to_participant_payload(),
                },
            )
        else:
            self.rooms.pop(meeting_id, None)

    async def handle_client_message(self, meeting_id: int, connection_id: str, message: dict[str, Any]) -> None:
        sender = self.find_connection_by_id(meeting_id, connection_id)
        if sender is None:
            return

        message_type = self.normalize_message_type(message.get("type"))
        if message_type == "ping":
            await self.send_to_connection(sender, {"type": "pong", "meetingId": meeting_id})
            return
        if message_type == "join":
            await self.send_snapshot(sender)
            return
        if message_type not in RELAY_MESSAGE_TYPES:
            await self.send_error(sender, "unsupported_message_type", "Unsupported signaling message type")
            return

        target_login_id = self.extract_target_login_id(message)
        target_connection_id = self.extract_target_connection_id(message)
        if message_type in TARGET_REQUIRED_MESSAGE_TYPES and target_login_id is None and target_connection_id is None:
            await self.send_error(sender, "target_required", "Target participant is required")
            return

        outgoing = {
            "type": message_type,
            "meetingId": meeting_id,
            "from": sender.login_id,
            "fromLoginId": sender.login_id,
            "fromRole": sender.role,
            "fromConnectionId": sender.connection_id,
            "payload": message.get("payload") or {},
        }
        if target_connection_id is not None:
            outgoing["toConnectionId"] = target_connection_id
            delivered = await self.send_to_connection_id(meeting_id, target_connection_id, outgoing)
            if not delivered:
                await self.send_error(sender, "participant_not_found", "Target participant is not connected")
            return

        if target_login_id is not None:
            outgoing["to"] = target_login_id
            outgoing["toLoginId"] = target_login_id
            delivered = await self.send_to_login_id(meeting_id, target_login_id, outgoing)
            if not delivered:
                await self.send_error(sender, "participant_not_found", "Target participant is not connected")
            return

        await self.broadcast(meeting_id, outgoing, exclude_connection_id=sender.connection_id)

    async def send_snapshot(self, connection: SignalingConnection) -> None:
        room = self.rooms.get(connection.meeting_id, {})
        await self.send_to_connection(
            connection,
            {
                "type": "participants_snapshot",
                "meetingId": connection.meeting_id,
                "self": connection.to_participant_payload(),
                "participants": [
                    participant.to_participant_payload()
                    for participant in room.values()
                    if participant.connection_id != connection.connection_id
                ],
            },
        )

    def find_connection_by_id(self, meeting_id: int, connection_id: str) -> SignalingConnection | None:
        room = self.rooms.get(meeting_id, {})
        for connection in room.values():
            if connection.connection_id == connection_id:
                return connection
        return None

    async def send_to_login_id(self, meeting_id: int, login_id: str, payload: dict[str, object]) -> bool:
        room = self.rooms.get(meeting_id, {})
        connection = room.get(login_id)
        if connection is None:
            return False
        await self.send_to_connection(connection, payload)
        return True

    async def send_to_connection_id(self, meeting_id: int, connection_id: str, payload: dict[str, object]) -> bool:
        connection = self.find_connection_by_id(meeting_id, connection_id)
        if connection is None:
            return False
        await self.send_to_connection(connection, payload)
        return True

    async def broadcast(
        self,
        meeting_id: int,
        payload: dict[str, object],
        exclude_connection_id: str | None = None,
    ) -> None:
        room = self.rooms.get(meeting_id, {})
        for connection in list(room.values()):
            if connection.connection_id == exclude_connection_id:
                continue
            await self.send_to_connection(connection, payload)

    async def send_error(self, connection: SignalingConnection, code: str, message: str) -> None:
        await self.send_to_connection(
            connection,
            {
                "type": "error",
                "meetingId": connection.meeting_id,
                "code": code,
                "message": message,
            },
        )

    async def send_to_connection(self, connection: SignalingConnection, payload: dict[str, object]) -> None:
        await connection.websocket.send_json(payload)

    async def safe_close(self, websocket: WebSocket, code: int, reason: str) -> None:
        try:
            await websocket.close(code=code, reason=reason)
        except RuntimeError:
            return

    def extract_target_login_id(self, message: dict[str, Any]) -> str | None:
        target = message.get("to") or message.get("targetLoginId") or message.get("targetLoginID") or message.get("target")
        return helpers.normalize_code(str(target)) if target is not None else None

    def extract_target_connection_id(self, message: dict[str, Any]) -> str | None:
        target = message.get("toConnectionId") or message.get("targetConnectionId") or message.get("targetConnectionID")
        return helpers.trim_to_none(str(target)) if target is not None else None

    def normalize_message_type(self, value: object) -> str:
        raw = str(value or "").strip()
        if raw in MESSAGE_TYPE_ALIASES:
            return MESSAGE_TYPE_ALIASES[raw]
        normalized = raw.replace("-", "_").lower()
        return MESSAGE_TYPE_ALIASES.get(normalized, normalized)

    def room_size(self, meeting_id: int) -> int:
        return len(self.rooms.get(meeting_id, {}))


signaling_manager = SignalingManager()
