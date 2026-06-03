from app.core.config import get_settings
from app.main import app


if __name__ == "__main__":
    import os

    import uvicorn

    settings = get_settings()
    port = int(os.getenv("PORT", settings.server_port))
    reload_enabled = settings.app_env == "development" and "PORT" not in os.environ
    uvicorn.run("main:app", host=settings.server_host, port=port, reload=reload_enabled)
