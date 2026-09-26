from fastapi import FastAPI

from app.accounts.router import router as accounts_router
from app.auth.rate_limit import RateLimiter
from app.auth.router import router as auth_router
from app.config import Settings, get_settings
from app.errors import register_error_handlers
from app.health import router as health_router
from app.imports.router import router as imports_router
from app.transactions.router import router as transactions_router


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Portfolio API")
    app.state.login_limiter = RateLimiter(settings.login_rate_limit_per_minute)
    app.state.register_limiter = RateLimiter(settings.register_rate_limit_per_minute)
    register_error_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(accounts_router)
    app.include_router(imports_router)
    app.include_router(transactions_router)
    return app


app = create_app()
