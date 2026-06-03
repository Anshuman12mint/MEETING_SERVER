# Meeting Server

FastAPI backend for college online meetings using WebRTC signaling.

This service should own meeting features only:

- Meeting room creation and joining
- College JWT verification
- WebSocket signaling for WebRTC
- Participant presence
- ICE/STUN/TURN configuration

Audio and video media are sent directly between browsers in the first P2P MVP. Chat should live in a separate chat service.

## Structure

```text
Meeting_server/
|-- app/
|   |-- api/
|   |-- common/
|   |-- core/
|   |-- db/
|   `-- modules/
|       `-- meetings/
|-- docs/
|-- scripts/
|-- tests/
|-- main.py
|-- requirements.txt
`-- .env.example
```

## Build Steps

1. Create the clean service structure. Done.
2. Add settings, logging, security middleware, and health endpoints. Done.
3. Add JWT validation compatible with `college_server`. Done.
4. Add meeting models, repositories, and migrations. Done.
5. Add meeting REST APIs. Done.
6. Add WebSocket signaling manager. Done.
7. Add WebRTC signaling protocol events and ICE config endpoint. Done.
8. Add cleanup/reliability behavior. Done.
9. Run final tests, route import checks, and server smoke checks. Done.

## Run Locally

```powershell
py -3.11 -m venv .venv-win
.\.venv-win\Scripts\activate
pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn main:app --reload --port 8001
```

Use `py -3.11` on this machine because the default `python` command points to MSYS2 Python.

Shortcut:

```powershell
.\scripts\run-dev.ps1
```

## Health Checks

```text
GET /health/live
GET /health/ready
GET /health
```

## Verify

```powershell
.\.venv-win\Scripts\python.exe -m unittest discover -s tests
.\.venv-win\Scripts\python.exe -m app.db.migrations --database-url sqlite+pysqlite:///:memory: upgrade head
.\.venv-win\Scripts\python.exe -B -c "from app.main import app; print(app.title); print(len(app.routes))"
```

## College JWT Auth

The meeting server does not create users or passwords. It trusts access tokens issued by `college_server`.

Use the same values in both services:

```env
JWT_SECRET=the-same-secret-as-college-server
JWT_ISSUER=college-server
JWT_AUDIENCE=college-clients
```

Verify a token:

```http
GET /api/auth/me
Authorization: Bearer <college_access_token>
```

## Database

Run migrations:

```powershell
.\.venv-win\Scripts\python.exe -m app.db.migrations upgrade head
```

Check migration status:

```powershell
.\.venv-win\Scripts\python.exe -m app.db.migrations status
```

## Meeting APIs

Teacher/Admin:

```http
POST /api/meetings
POST /api/meetings/{meetingId}/end
```

Authenticated users:

```http
GET /api/meetings
GET /api/meetings/{meetingId}
POST /api/meetings/{meetingId}/join
```

Join returns the participant record, WebSocket URL, and ICE server config for the frontend WebRTC flow. The participant is marked connected only after the WebSocket opens.

## WebSocket Signaling

Get frontend ICE/protocol config:

```http
GET /api/meetings/ice-config
Authorization: Bearer <college_access_token>
```

```text
WS /ws/meetings/{meetingId}?token=<college_access_token>
```

The server sends:

```json
{ "type": "participants_snapshot", "participants": [] }
```

Clients relay WebRTC messages with:

```json
{
  "type": "offer",
  "to": "STU-00001",
  "payload": {}
}
```

Supported signaling types:

- `join`
- `ping`
- `offer`
- `answer`
- `ice_candidate`
- `mute_state`
- `camera_state`

The WebSocket also accepts frontend aliases like `iceCandidate`, `muteState`, and `cameraState`.

## Reliability Behavior

- Duplicate WebSocket connections for the same login replace the old socket.
- Stale disconnects do not mark a newer reconnect as disconnected.
- Participant connection state is updated when the WebSocket opens/closes.
- Active meetings with no connected participants are auto-ended after `MEETING_IDLE_TIMEOUT_SECONDS`.
