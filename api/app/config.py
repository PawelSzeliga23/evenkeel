from functools import lru_cache
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEV_DEFAULT_JWT_SECRET = "dev-only-insecure-secret-change-me-0123456789"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://portfolio:portfolio@localhost:5432/portfolio"
    jwt_secret: str = _DEV_DEFAULT_JWT_SECRET
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

    @model_validator(mode="after")
    def _reject_weak_jwt_secret_outside_local_dev(self) -> Self:
        # cookie_secure is only false in local dev (docker-compose sets COOKIE_SECURE=false);
        # everywhere else, the published default secret or a too-short one would let anyone
        # forge access tokens.
        if self.cookie_secure and (
            self.jwt_secret == _DEV_DEFAULT_JWT_SECRET or len(self.jwt_secret.encode()) < 32
        ):
            raise ValueError(
                "JWT_SECRET must be set to a unique secret of at least 32 bytes when "
                "COOKIE_SECURE is true. Set the JWT_SECRET environment variable."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
