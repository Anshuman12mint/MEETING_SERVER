from fastapi import APIRouter

from app.api.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.meetings.router import router as meetings_router
from app.modules.meetings.websocket_router import router as meeting_websocket_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(meetings_router)
api_router.include_router(meeting_websocket_router)
