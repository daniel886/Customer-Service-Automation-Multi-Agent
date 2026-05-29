"""Auth helpers (JWT)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from core.config import settings


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/admin/login", auto_error=False)


def create_access_token(subject: str) -> tuple[str, int]:
    expire_minutes = settings.jwt_expire_minutes
    expire = datetime.now(tz=timezone.utc) + timedelta(minutes=expire_minutes)
    payload = {"sub": subject, "exp": expire}
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return token, expire_minutes * 60


def verify_credentials(username: str, password: str) -> bool:
    return username == settings.admin_username and password == settings.admin_password


def get_current_admin(token: Optional[str] = Depends(oauth2_scheme)) -> str:
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing token")
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, f"Invalid token: {exc}") from exc
    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token payload")
    return sub
