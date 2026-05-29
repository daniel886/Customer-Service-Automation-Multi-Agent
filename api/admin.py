"""Admin login + JWT token endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from api.auth import create_access_token, get_current_admin, verify_credentials
from models.schemas import LoginRequest, TokenResponse


router = APIRouter()


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest) -> TokenResponse:
    if not verify_credentials(body.username, body.password):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    token, expires = create_access_token(body.username)
    return TokenResponse(access_token=token, expires_in=expires)


@router.get("/me")
async def me(admin: str = Depends(get_current_admin)) -> dict:
    return {"username": admin}
