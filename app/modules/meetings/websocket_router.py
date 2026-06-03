from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from sqlalchemy.orm import Session

from app.db.session import session_context
from app.modules.auth.dependencies import authenticate_token
from app.modules.meetings.repository import MeetingEventRepository, MeetingParticipantRepository, MeetingRepository
from app.modules.meetings.service import MeetingService
from app.modules.meetings.signaling import signaling_manager


router = APIRouter(tags=["signaling"])
logger = logging.getLogger(__name__)


@router.websocket("/ws/meetings/{meeting_id}")
async def meeting_signaling_websocket(
    websocket: WebSocket,
    meeting_id: int,
    token: str | None = Query(default=None),
    display_name: str | None = Query(default=None, alias="displayName"),
) -> None:
    principal = authenticate_token(token)
    if principal is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Authentication is required")
        return

    try:
        with session_context() as session:
            participant = build_meeting_service(session).open_signaling_connection(meeting_id, principal, display_name)
    except HTTPException as exc:
        message = exc.detail if isinstance(exc.detail, str) else "Meeting is not open"
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason=message)
        return

    connection = await signaling_manager.connect(
        meeting_id,
        websocket,
        principal,
        display_name=participant.display_name,
        connection_id=participant.connection_id,
    )
    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                await signaling_manager.send_error(connection, "invalid_message", "Signaling message must be a JSON object")
                continue
            await signaling_manager.handle_client_message(meeting_id, connection.connection_id, message)
    except WebSocketDisconnect:
        await signaling_manager.disconnect(meeting_id, principal.login_id, connection.connection_id)
        close_signaling_connection(meeting_id, principal.login_id, connection.connection_id)
    except Exception:
        logger.exception("websocket_signaling_failed meeting_id=%s login_id=%s", meeting_id, principal.login_id)
        await signaling_manager.disconnect(meeting_id, principal.login_id, connection.connection_id)
        close_signaling_connection(meeting_id, principal.login_id, connection.connection_id)
        await close_after_error(websocket)


def build_meeting_service(session: Session) -> MeetingService:
    return MeetingService(
        MeetingRepository(session),
        MeetingParticipantRepository(session),
        MeetingEventRepository(session),
    )


def close_signaling_connection(meeting_id: int, login_id: str, connection_id: str) -> bool:
    with session_context() as session:
        return build_meeting_service(session).close_signaling_connection(meeting_id, login_id, connection_id)


async def close_after_error(websocket: WebSocket) -> None:
    try:
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Signaling failed")
    except RuntimeError:
        return
