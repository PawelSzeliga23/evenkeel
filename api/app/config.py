from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://portfolio:portfolio@localhost:5432/portfolio"
    jwt_secret: str = "dev-only-insecure-secret-change-me-0123456789"
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    cookie_secure: bool = True
    registration_mode: Literal["open", "invite"] = "open"
    invite_codes: str = ""
    login_rate_limit_per_minute: int = 10
    register_rate_limit_per_minute: int = 5

    @property
    def invite_code_set(self) -> frozenset[str]:
        return frozenset(code.strip() for code in self.invite_codes.split(",") if code.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
