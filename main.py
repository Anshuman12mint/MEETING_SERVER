from app.core.config import get_settings
from app.main import app


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run("main:app", host=settings.server_host, port=settings.server_port, reload=settings.app_env == "development")
