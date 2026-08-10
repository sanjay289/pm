import secrets
from typing import Annotated

from fastapi import Cookie, HTTPException, status

USERNAME = "user"
PASSWORD = "password"
SESSION_COOKIE = "session_id"

_sessions: set[str] = set()


def verify_credentials(username: str, password: str) -> bool:
    return username == USERNAME and password == PASSWORD


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _sessions.add(token)
    return token


def destroy_session(token: str | None) -> None:
    if token:
        _sessions.discard(token)


def is_valid_session(token: str | None) -> bool:
    return token is not None and token in _sessions


def require_session(session_id: Annotated[str | None, Cookie()] = None) -> str:
    if not is_valid_session(session_id):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return session_id
