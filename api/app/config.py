from functools import lru_cache
from typing import Literal

from fastapi import Request
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

HH_MM = r"^([01]\d|2[0-3]):[0-5]\d$"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://portfolio:portfolio@localhost:5432/portfolio"
    jwt_secret: str = Field(min_length=32)
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = True
    registration_mode: Literal["open", "invite"] = "invite"  # open only on purpose: e.g. a local copy
    invite_codes: str = ""
    # Behind a proxy (Cloudflare Tunnel) every request comes from the proxy; its header carries the real client IP
    # for the rate limits. Set it (e.g. CF-Connecting-IP) only when the API is reachable through that proxy alone,
    # since anyone talking to the API directly could write the header themselves.
    client_ip_header: str = ""
    login_rate_limit_per_minute: int = 10
    login_failures_per_email_per_minute: int = 20  # wrong passwords for one e-mail, from any IP
    register_rate_limit_per_minute: int = 5
    catalog_add_rate_limit_per_minute: int = 10  # each new ticker is fetched now and by the worker for good
    market_daily_at: str = Field(default="23:00", pattern=HH_MM)
    market_timezone: str = "Europe/Warsaw"
    market_intraday_minutes: int = Field(default=30, ge=5)
    market_intraday_from: str = Field(default="09:00", pattern=HH_MM)
    market_intraday_to: str = Field(default="22:30", pattern=HH_MM)
    worker_poll_seconds: int = Field(default=300, ge=10)

    @property
    def invite_code_set(self) -> frozenset[str]:
        return frozenset(code.strip() for code in self.invite_codes.split(",") if code.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()


def app_settings(request: Request) -> Settings:
    """The settings the app was created with (`create_app`), for routes."""
    return request.app.state.settings
