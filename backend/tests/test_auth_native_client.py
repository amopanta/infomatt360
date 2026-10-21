"""Refresh token for the native mobile app vs. the web's httponly cookie."""

from app.core.config import settings
from test_auth_session import auth_client  # noqa: F401  (fixture)

NATIVE = {"X-Client-Platform": "native"}
CREDENTIALS = {"email": "ana@example.com", "password": "Clave123"}


def test_native_login_returns_refresh_token_in_body_without_cookie(auth_client):  # noqa: F811
    login = auth_client.post("/api/v1/auth/login", json=CREDENTIALS, headers=NATIVE)
    assert login.status_code == 200, login.text
    assert login.json()["access_token"]
    assert login.json()["refresh_token"]
    assert not auth_client.cookies.get(settings.refresh_cookie_name)


def test_native_refresh_rotates_token_in_body(auth_client):  # noqa: F811
    first = auth_client.post("/api/v1/auth/login", json=CREDENTIALS, headers=NATIVE).json()["refresh_token"]

    rotated = auth_client.post("/api/v1/auth/refresh", json={"refresh_token": first}, headers=NATIVE)
    assert rotated.status_code == 200, rotated.text
    second = rotated.json()["refresh_token"]
    assert second and second != first

    # El token ya usado queda invalidado por la rotación.
    assert auth_client.post("/api/v1/auth/refresh", json={"refresh_token": first}, headers=NATIVE).status_code == 401


def test_browser_cannot_use_native_mode(auth_client):  # noqa: F811
    # Un navegador siempre envía Origin en un POST: aunque agregue el
    # encabezado nativo, el refresh token sigue solo en la cookie httponly.
    login = auth_client.post("/api/v1/auth/login", json=CREDENTIALS, headers={**NATIVE, "Origin": "http://localhost:5173"})
    assert login.status_code == 200, login.text
    assert login.json()["refresh_token"] is None
    assert auth_client.cookies.get(settings.refresh_cookie_name)


def test_web_login_unchanged(auth_client):  # noqa: F811
    login = auth_client.post("/api/v1/auth/login", json=CREDENTIALS)
    assert login.json()["refresh_token"] is None
    assert auth_client.cookies.get(settings.refresh_cookie_name)
