import time

from fastapi import Depends
from fastapi.testclient import TestClient
from jose import jwt

from api.deps import ALGORITHM, get_current_user
from api.main import app
from core.config import settings

# Test-only protected probe so auth can be verified before protected routes exist.
@app.get("/_protected", include_in_schema=False)
async def _protected(user: str = Depends(get_current_user)) -> dict[str, str]:
    return {"user": user}


client = TestClient(app)


def _issue_token() -> str:
    resp = client.post(
        "/auth/token",
        json={"username": settings.demo_username, "password": settings.demo_password},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


def test_token_issuance_json() -> None:
    resp = client.post(
        "/auth/token",
        json={"username": settings.demo_username, "password": settings.demo_password},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == settings.jwt_ttl_minutes * 60
    assert body["access_token"]


def test_token_issuance_oauth2_form() -> None:
    resp = client.post(
        "/auth/token",
        data={"username": settings.demo_username, "password": settings.demo_password},
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


def test_token_wrong_password() -> None:
    resp = client.post(
        "/auth/token",
        json={"username": settings.demo_username, "password": "wrong"},
    )
    assert resp.status_code == 401
    assert "detail" in resp.json()


def test_protected_route_with_valid_token() -> None:
    token = _issue_token()
    resp = client.get("/_protected", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["user"] == settings.demo_username


def test_missing_header_is_401() -> None:
    resp = client.get("/_protected")
    assert resp.status_code == 401


def test_garbage_token_is_401() -> None:
    resp = client.get("/_protected", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


def test_expired_token_is_401() -> None:
    now = int(time.time())
    expired = jwt.encode(
        {"sub": settings.demo_username, "iat": now - 7200, "exp": now - 3600},
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    resp = client.get("/_protected", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_health_requires_no_auth() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"
