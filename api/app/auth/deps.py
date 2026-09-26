from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token, invalid_token
from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import User

_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if credentials is None:
        raise ApiError(401, "not_authenticated", "Wymagane logowanie.")
    user = db.get(User, decode_access_token(credentials.credentials, settings))
    if user is None:
        raise invalid_token()
    return user
