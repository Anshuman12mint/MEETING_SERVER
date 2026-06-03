from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db_session
from app.modules.auth.dependencies import get_current_principal, require_roles
from app.modules.auth.schemas import AuthenticatedPrincipal
from app.modules.meetings.repository import MeetingEventRepository, MeetingParticipantRepository, MeetingRepository
from app.modules.meetings.schemas import (
    IceConfigResponse,
    IceServerRead,
    MeetingCreateRequest,
    MeetingEndRequest,
    MeetingJoinRequest,
    MeetingJoinResponse,
    MeetingRead,
    SignalingProtocolRead,
)
from app.modules.meetings.service import MeetingService
from app.modules.meetings.signaling import CLIENT_MESSAGE_TYPES, SERVER_MESSAGE_TYPES, TARGET_REQUIRED_MESSAGE_TYPES


router = APIRouter(prefix="/api/meetings", tags=["meetings"])


def get_meeting_service(session: Session = Depends(get_db_session)) -> MeetingService:
    return MeetingService(
        MeetingRepository(session),
        MeetingParticipantRepository(session),
        MeetingEventRepository(session),
    )


@router.get("", response_model=list[MeetingRead])
def get_meetings(
    status_filter: str | None = Query(default=None, alias="status"),
    search: str | None = Query(default=None),
    current_principal: AuthenticatedPrincipal = Depends(get_current_principal),
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> list[MeetingRead]:
    _ = current_principal
    return meeting_service.get_meetings(status_filter=status_filter, search=search)


@router.post("", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
def create_meeting(
    request: MeetingCreateRequest,
    current_principal: AuthenticatedPrincipal = Depends(require_roles("Teacher", "Admin")),
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingRead:
    return meeting_service.create_meeting(request, current_principal)


@router.get("/ice-config", response_model=IceConfigResponse)
def get_ice_config(
    current_principal: AuthenticatedPrincipal = Depends(get_current_principal),
) -> IceConfigResponse:
    _ = current_principal
    settings = get_settings()
    return IceConfigResponse(
        ice_servers=[IceServerRead(urls=url) for url in settings.ice_server_urls],
        signaling=SignalingProtocolRead(
            ws_path="/ws/meetings/{meetingId}?token=<college_access_token>",
            client_message_types=sorted(CLIENT_MESSAGE_TYPES),
            server_message_types=sorted(SERVER_MESSAGE_TYPES),
            target_required_types=sorted(TARGET_REQUIRED_MESSAGE_TYPES),
            target_fields=["to", "targetLoginId", "toConnectionId", "targetConnectionId"],
        ),
    )


@router.get("/{meeting_id}", response_model=MeetingRead)
def get_meeting(
    meeting_id: int,
    current_principal: AuthenticatedPrincipal = Depends(get_current_principal),
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingRead:
    _ = current_principal
    return meeting_service.get_meeting(meeting_id)


@router.post("/{meeting_id}/join", response_model=MeetingJoinResponse)
def join_meeting(
    meeting_id: int,
    request: MeetingJoinRequest,
    http_request: Request,
    current_principal: AuthenticatedPrincipal = Depends(get_current_principal),
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingJoinResponse:
    token = extract_bearer_token(http_request)
    ws_url = build_meeting_ws_url(http_request, meeting_id, token)
    return meeting_service.join_meeting(meeting_id, request, current_principal, ws_url)


@router.post("/{meeting_id}/end", response_model=MeetingRead)
def end_meeting(
    meeting_id: int,
    request: MeetingEndRequest,
    current_principal: AuthenticatedPrincipal = Depends(require_roles("Teacher", "Admin")),
    meeting_service: MeetingService = Depends(get_meeting_service),
) -> MeetingRead:
    return meeting_service.end_meeting(meeting_id, request, current_principal)


def extract_bearer_token(request: Request) -> str:
    authorization = request.headers.get("authorization", "")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer":
        return ""
    return token.strip()


def build_meeting_ws_url(request: Request, meeting_id: int, token: str) -> str:
    scheme = "wss" if request.url.scheme == "https" else "ws"
    return f"{scheme}://{request.url.netloc}/ws/meetings/{meeting_id}?token={quote(token, safe='')}"
