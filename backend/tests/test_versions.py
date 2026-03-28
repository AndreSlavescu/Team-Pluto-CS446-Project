"""Tests for the version history endpoints."""

from __future__ import annotations

import os
import zipfile

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _setup_env(tmp_path):
    """Set required env vars and use a temp data dir so tests don't touch real data."""
    os.environ["OPENAI_API_KEY"] = "test-key"
    os.environ["JWT_SECRET"] = "test-secret-key-for-jwt-signing"
    os.environ["DATA_DIR"] = str(tmp_path)
    os.environ["STATE_PATH"] = str(tmp_path / "state.json")
    os.environ["DATABASE_PUBLIC_URL"] = ""

    import importlib

    from app import config, database, store

    importlib.reload(config)
    importlib.reload(store)

    store.store = store.DataStore(config.STATE_PATH)

    importlib.reload(database)
    database.init_db()

    from app import auth, main

    importlib.reload(auth)
    importlib.reload(main)

    yield


@pytest.fixture
def client():
    from app.main import app

    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def auth_header(client):
    """Register a user and return auth header."""
    resp = client.post(
        "/v1/auth/register",
        json={"email": "test@example.com", "password": "securepass123"},
    )
    token = resp.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def _create_app_with_versions(tmp_path, n_versions=3):
    """Directly create an app with n versions in the store."""
    from app.store import store

    app_record = store.create_app(owner_id="test-owner")
    app_id = app_record["appId"]

    version_ids = []
    for i in range(n_versions):
        # Create a real ZIP artifact so _artifact_response can compute sha256
        zip_path = tmp_path / f"artifact_{i}.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("index.html", f"<html>Version {i + 1}</html>")

        artifact = store.create_artifact(
            artifact_type="project_zip",
            path=zip_path,
            ttl_hours=1,
        )
        version = store.create_version(
            app_id=app_id,
            job_id=f"job_fake_{i}",
            manifest={
                "displayName": f"Test App v{i + 1}",
                "packageName": "com.test.app",
                "features": ["feature1"],
                "ui": "material",
            },
            artifacts=[artifact],
        )
        version_ids.append(version["versionId"])

    return app_id, version_ids


class TestGetLatestVersion:
    def test_latest_version_success(self, client, auth_header, tmp_path):
        app_id, version_ids = _create_app_with_versions(tmp_path, n_versions=3)
        resp = client.get(f"/v1/apps/{app_id}/versions/latest", headers=auth_header)
        assert resp.status_code == 200
        body = resp.json()
        assert body["versionId"] == version_ids[-1]
        assert body["manifest"]["displayName"] == "Test App v3"
        assert len(body["artifacts"]) == 1
        assert body["artifacts"][0]["type"] == "project_zip"
        assert "downloadUrl" in body["artifacts"][0]

    def test_latest_version_app_not_found(self, client, auth_header):
        resp = client.get(
            "/v1/apps/app_0000000000000000/versions/latest", headers=auth_header
        )
        assert resp.status_code == 404

    def test_latest_version_no_versions(self, client, auth_header):
        from app.store import store

        app_record = store.create_app(owner_id="test-owner")
        resp = client.get(
            f"/v1/apps/{app_record['appId']}/versions/latest",
            headers=auth_header,
        )
        assert resp.status_code == 404


class TestListVersions:
    def test_list_versions_success(self, client, auth_header, tmp_path):
        app_id, version_ids = _create_app_with_versions(tmp_path, n_versions=3)
        resp = client.get(f"/v1/apps/{app_id}/versions", headers=auth_header)
        assert resp.status_code == 200
        body = resp.json()
        assert body["appId"] == app_id
        assert len(body["versions"]) == 3
        # Versions should be in creation order
        for i, version in enumerate(body["versions"]):
            assert version["versionId"] == version_ids[i]
            assert version["manifest"]["displayName"] == f"Test App v{i + 1}"

    def test_list_versions_with_limit(self, client, auth_header, tmp_path):
        app_id, version_ids = _create_app_with_versions(tmp_path, n_versions=5)
        resp = client.get(f"/v1/apps/{app_id}/versions?limit=2", headers=auth_header)
        assert resp.status_code == 200
        body = resp.json()
        # limit=2 returns the last 2 versions (most recent)
        assert len(body["versions"]) == 2
        assert body["versions"][0]["versionId"] == version_ids[3]
        assert body["versions"][1]["versionId"] == version_ids[4]

    def test_list_versions_app_not_found(self, client, auth_header):
        resp = client.get("/v1/apps/app_0000000000000000/versions", headers=auth_header)
        assert resp.status_code == 404

    def test_list_versions_empty(self, client, auth_header):
        from app.store import store

        app_record = store.create_app(owner_id="test-owner")
        resp = client.get(
            f"/v1/apps/{app_record['appId']}/versions", headers=auth_header
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["appId"] == app_record["appId"]
        assert body["versions"] == []

    def test_list_versions_single_version(self, client, auth_header, tmp_path):
        app_id, version_ids = _create_app_with_versions(tmp_path, n_versions=1)
        resp = client.get(f"/v1/apps/{app_id}/versions", headers=auth_header)
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["versions"]) == 1
        assert body["versions"][0]["versionId"] == version_ids[0]

    def test_list_versions_contains_artifacts(self, client, auth_header, tmp_path):
        app_id, _ = _create_app_with_versions(tmp_path, n_versions=1)
        resp = client.get(f"/v1/apps/{app_id}/versions", headers=auth_header)
        body = resp.json()
        version = body["versions"][0]
        assert len(version["artifacts"]) == 1
        artifact = version["artifacts"][0]
        assert artifact["type"] == "project_zip"
        assert "downloadUrl" in artifact
        assert "sha256" in artifact

    def test_list_versions_contains_manifest(self, client, auth_header, tmp_path):
        app_id, _ = _create_app_with_versions(tmp_path, n_versions=1)
        resp = client.get(f"/v1/apps/{app_id}/versions", headers=auth_header)
        body = resp.json()
        manifest = body["versions"][0]["manifest"]
        assert manifest["displayName"] == "Test App v1"
        assert manifest["packageName"] == "com.test.app"
        assert manifest["features"] == ["feature1"]
        assert manifest["ui"] == "material"

    def test_list_versions_order_is_chronological(self, client, auth_header, tmp_path):
        app_id, version_ids = _create_app_with_versions(tmp_path, n_versions=4)
        resp = client.get(f"/v1/apps/{app_id}/versions", headers=auth_header)
        body = resp.json()
        # Versions should be in chronological order (oldest first)
        returned_ids = [v["versionId"] for v in body["versions"]]
        assert returned_ids == version_ids

    def test_latest_version_matches_last_in_list(self, client, auth_header, tmp_path):
        """The latest version endpoint should return the same version as the last in the list."""
        app_id, _ = _create_app_with_versions(tmp_path, n_versions=3)

        latest_resp = client.get(
            f"/v1/apps/{app_id}/versions/latest", headers=auth_header
        )
        list_resp = client.get(f"/v1/apps/{app_id}/versions", headers=auth_header)

        latest = latest_resp.json()
        versions = list_resp.json()["versions"]

        assert latest["versionId"] == versions[-1]["versionId"]
