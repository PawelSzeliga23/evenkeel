from fastapi import FastAPI

from app.config import Settings, get_settings
from app.errors import register_error_handlers
from app.health import router as health_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Portfolio API")
    register_error_handlers(app)
    app.include_router(health_router)
    return app


app = create_app()
