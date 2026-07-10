"""Token issuance. Accepts both JSON bodies and OAuth2 password-flow form data
so the Swagger Authorize button works against the same endpoint."""

import json
import time

from fastapi import APIRouter, HTTPException, Request, status
from jose import jwt
from pydantic import ValidationError

from api.deps import ALGORITHM
from api.schemas import TokenRequest, TokenResponse
from core.config import settings

router = APIRouter()


def create_access_token(subject: str) -> tuple[str, int]:
    """Return (token, expires_in_seconds)."""
    expires_in = settings.jwt_ttl_minutes * 60
    now = int(time.time())
    payload = {"sub": subject, "iat": now, "exp": now + expires_in}
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), expires_in


async def _parse_credentials(request: Request) -> TokenRequest:
    """Accept JSON, raw-JSON-as-form (curl -d), or OAuth2 form fields."""
    raw = await request.body()
    try:
        return TokenRequest.model_validate(json.loads(raw))
    except (json.JSONDecodeError, UnicodeDecodeError, ValidationError):
        pass
    form = await request.form()
    try:
        return TokenRequest(username=str(form.get("username", "")), password=str(form.get("password", "")))
    except ValidationError:
        raise HTTPException(status_code=422, detail="username and password are required")


@router.post("/auth/token", response_model=TokenResponse)
async def issue_token(request: Request) -> TokenResponse:
    creds = await _parse_credentials(request)
    if creds.username != settings.demo_username or creds.password != settings.demo_password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_access_token(creds.username)
    return TokenResponse(access_token=token, expires_in=expires_in)
