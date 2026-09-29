from fastapi import FastAPI

from app.accounts.router import router as accounts_router
from app.auth.rate_limit import RateLimiter
from app.auth.router import router as auth_router
from app.bonds.router import router as bonds_router
from app.config import Settings, get_settings
from app.corporate_actions.router import router as corporate_actions_router
from app.errors import register_error_handlers
from app.health import router as health_router
from app.history.router import router as history_router
from app.imports.router import router as imports_router
from app.instruments.router import router as instruments_router
from app.portfolio.router import router as portfolio_router
from app.savings.router import create_router as savings_create_router
from app.savings.router import router as savings_router
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
    app.include_router(instruments_router)
    app.include_router(corporate_actions_router)
    app.include_router(bonds_router)
    app.include_router(savings_create_router)
    app.include_router(savings_router)
    app.include_router(portfolio_router)
    app.include_router(history_router)
    return app


app = create_app()
