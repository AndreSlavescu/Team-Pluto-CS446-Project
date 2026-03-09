"""Tests for the auth endpoints (register, login, refresh, me, logout, delete)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _setup_env(tmp_path):
    """Set required env vars and use a temp data dir so tests don't touch real data."""
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["JWT_SECRET"] = "test-secret-key-for-jwt-signing"
    os.environ["DATA_DIR"] = str(tmp_path)
    os.environ["STATE_PATH"] = str(tmp_path / "state.json")
    os.environ["DATABASE_PUBLIC_URL"] = ""  # Use in-memory fallback

    # Reload modules so they pick up the new env vars
    import importlib

    from app import config, database, store

    importlib.reload(config)
    importlib.reload(store)

    # Re-initialize store with the fresh config
    store.store = store.DataStore(config.STATE_PATH)

    # Initialize database (in-memory mode since DATABASE_URL is empty)
    importlib.reload(database)
    database.init_db()

    # Now reload main so it picks up the fresh modules
    from app import auth, main

    importlib.reload(auth)
    importlib.reload(main)

    yield


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


def _register(client, email="test@example.com", password="securepass123"):
    return client.post("/v1/auth/register", json={"email": email, "password": password})


def _login(client, email="test@example.com", password="securepass123"):
    return client.post("/v1/auth/login", json={"email": email, "password": password})


def _auth_header(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}"}


class TestRegister:
    def test_register_success(self, client):
        resp = _register(client)
        assert resp.status_code == 200
        body = resp.json()
        assert "accessToken" in body
        assert "refreshToken" in body
        assert body["tokenType"] == "bearer"
        assert body["expiresIn"] > 0

    def test_register_duplicate_email(self, client):
        _register(client)
        resp = _register(client)
        assert resp.status_code == 409
        assert resp.json()["detail"]["code"] == "EMAIL_TAKEN"

    def test_register_invalid_email(self, client):
        resp = _register(client, email="notanemail")
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "INVALID_EMAIL"

    def test_register_short_password(self, client):
        resp = _register(client, password="short")
        assert resp.status_code == 400
        assert resp.json()["detail"]["code"] == "WEAK_PASSWORD"


class TestLogin:
    def test_login_success(self, client):
        _register(client)
        resp = _login(client)
        assert resp.status_code == 200
        body = resp.json()
        assert "accessToken" in body
        assert "refreshToken" in body

    def test_login_wrong_password(self, client):
        _register(client)
        resp = _login(client, password="wrongpassword")
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "INVALID_CREDENTIALS"

    def test_login_nonexistent_user(self, client):
        resp = _login(client, email="nobody@example.com")
        assert resp.status_code == 401
        assert resp.json()["detail"]["code"] == "INVALID_CREDENTIALS"


class TestRefresh:
    def test_refresh_success(self, client):
        reg = _register(client).json()
        resp = client.post(
            "/v1/auth/refresh",
            json={"refreshToken": reg["refreshToken"]},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "accessToken" in body
        assert "refreshToken" in body
        # Old refresh token should be invalidated (rotated)
        resp2 = client.post(
            "/v1/auth/refresh",
            json={"refreshToken": reg["refreshToken"]},
        )
        assert resp2.status_code == 401

    def test_refresh_invalid_token(self, client):
        resp = client.post(
            "/v1/auth/refresh",
            json={"refreshToken": "bogus-token"},
        )
        assert resp.status_code == 401


class TestMe:
    def test_me_success(self, client):
        reg = _register(client).json()
        resp = client.get("/v1/auth/me", headers=_auth_header(reg["accessToken"]))
        assert resp.status_code == 200
        body = resp.json()
        assert body["email"] == "test@example.com"
        assert "userId" in body

    def test_me_no_token(self, client):
        resp = client.get("/v1/auth/me")
        assert resp.status_code == 401

    def test_me_invalid_token(self, client):
        resp = client.get("/v1/auth/me", headers=_auth_header("invalid-token"))
        assert resp.status_code == 401


class TestLogout:
    def test_logout_success(self, client):
        reg = _register(client).json()
        resp = client.post(
            "/v1/auth/logout",
            json={"refreshToken": reg["refreshToken"]},
            headers=_auth_header(reg["accessToken"]),
        )
        assert resp.status_code == 200
        # Refresh token should be revoked
        resp2 = client.post(
            "/v1/auth/refresh",
            json={"refreshToken": reg["refreshToken"]},
        )
        assert resp2.status_code == 401


class TestDeleteAccount:
    def test_delete_account_success(self, client):
        reg = _register(client).json()
        resp = client.delete(
            "/v1/auth/account",
            headers=_auth_header(reg["accessToken"]),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Should not be able to login anymore
        resp2 = _login(client)
        assert resp2.status_code == 401

    def test_delete_account_no_auth(self, client):
        resp = client.delete("/v1/auth/account")
        assert resp.status_code == 401
