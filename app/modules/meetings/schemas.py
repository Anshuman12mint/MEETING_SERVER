from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class MeetingCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meeting_code: str | None = Field(default=None, validation_alias=AliasChoices("meetingCode", "meeting_code"))
    title: str
    description: str | None = None
    starts_at: datetime | None = Field(default=None, validation_alias=AliasChoices("startsAt", "starts_at"))
    max_participants: int | None = Field(default=None, ge=1, validation_alias=AliasChoices("maxParticipants", "max_participants"))


class MeetingEndRequest(BaseModel):
    reason: str | None = None


class MeetingJoinRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    display_name: str | None = Field(default=None, validation_alias=AliasChoices("displayName", "display_name"))


class MeetingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    meeting_id: int | None = Field(default=None, serialization_alias="meetingId")
    meeting_code: str | None = Field(default=None, serialization_alias="meetingCode")
    title: str | None = None
    description: str | None = None
    created_by_login_id: str | None = Field(default=None, serialization_alias="createdByLoginId")
    created_by_role: str | None = Field(default=None, serialization_alias="createdByRole")
    status: str | None = None
    starts_at: datetime | None = Field(default=None, serialization_alias="startsAt")
    ended_at: datetime | None = Field(default=None, serialization_alias="endedAt")
    max_participants: int | None = Field(default=None, serialization_alias="maxParticipants")
    created_at: datetime | None = Field(default=None, serialization_alias="createdAt")
    updated_at: datetime | None = Field(default=None, serialization_alias="updatedAt")


class MeetingParticipantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    participant_id: int | None = Field(default=None, serialization_alias="participantId")
    meeting_id: int | None = Field(default=None, serialization_alias="meetingId")
    login_id: str | None = Field(default=None, serialization_alias="loginId")
    role: str | None = None
    display_name: str | None = Field(default=None, serialization_alias="displayName")
    connection_id: str | None = Field(default=None, serialization_alias="connectionId")
    joined_at: datetime | None = Field(default=None, serialization_alias="joinedAt")
    last_seen_at: datetime | None = Field(default=None, serialization_alias="lastSeenAt")
    left_at: datetime | None = Field(default=None, serialization_alias="leftAt")
    is_connected: bool = Field(default=False, serialization_alias="isConnected")
    audio_muted: bool = Field(default=False, serialization_alias="audioMuted")
    video_enabled: bool = Field(default=True, serialization_alias="videoEnabled")


class IceServerRead(BaseModel):
    urls: str


class SignalingProtocolRead(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ws_path: str = Field(serialization_alias="wsPath")
    client_message_types: list[str] = Field(serialization_alias="clientMessageTypes")
    server_message_types: list[str] = Field(serialization_alias="serverMessageTypes")
    target_required_types: list[str] = Field(serialization_alias="targetRequiredTypes")
    target_fields: list[str] = Field(serialization_alias="targetFields")
    payload_field: str = Field(default="payload", serialization_alias="payloadField")


class IceConfigResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    ice_servers: list[IceServerRead] = Field(serialization_alias="iceServers")
    signaling: SignalingProtocolRead


class MeetingJoinResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    meeting: MeetingRead
    participant: MeetingParticipantRead
    ws_url: str = Field(serialization_alias="wsUrl")
    ice_servers: list[IceServerRead] = Field(serialization_alias="iceServers")
