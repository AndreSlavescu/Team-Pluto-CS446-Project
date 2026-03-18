"""Tests for the per-app sandboxed database feature."""

from __future__ import annotations

import importlib
import os
from unittest.mock import MagicMock, patch
from zipfile import ZipFile

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

    from app import config, database, store

    importlib.reload(config)
    importlib.reload(store)
    store.store = store.DataStore(config.STATE_PATH)
    importlib.reload(database)
    database.init_db()

    from app import appdb, appdb_routes, auth, main

    importlib.reload(auth)
    importlib.reload(appdb)
    importlib.reload(appdb_routes)
    importlib.reload(main)

    yield

    # Close any open SQLite connections
    appdb._pool.close_all()


@pytest.fixture()
def client():
    from app.main import app

    # Deduplicate routes that may accumulate from reloads
    seen = set()
    unique_routes = []
    for route in app.routes:
        key = (
            getattr(route, "path", None),
            frozenset(getattr(route, "methods", set()) or set()),
        )
        if key not in seen:
            seen.add(key)
            unique_routes.append(route)
    app.routes[:] = unique_routes

    return TestClient(app)


@pytest.fixture()
def authed_user(client):
    """Register a user and return (headers, user_id)."""
    resp = client.post(
        "/v1/auth/register",
        json={"email": "test@example.com", "password": "password123"},
    )
    assert resp.status_code == 200
    token = resp.json()["accessToken"]
    # Get user ID
    me_resp = client.get("/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    user_id = me_resp.json()["userId"]
    return {"Authorization": f"Bearer {token}"}, user_id


@pytest.fixture()
def app_with_owner(authed_user):
    """Create an app with an owner and return (headers, app_id)."""
    from app.store import store

    headers, user_id = authed_user
    app_record = store.create_app(owner_id=user_id)
    return headers, app_record["appId"]


# ---- Unit tests for appdb module ----


class TestAppDBUnit:
    def test_create_and_list_items(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner

        item = appdb.create_item(app_id, "todos", {"title": "Buy milk", "done": False})
        assert "id" in item
        assert item["data"]["title"] == "Buy milk"

        result = appdb.list_items(app_id, "todos")
        assert result["total"] == 1
        assert result["items"][0]["data"]["title"] == "Buy milk"

    def test_get_item(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        created = appdb.create_item(app_id, "notes", {"text": "hello"})
        fetched = appdb.get_item(app_id, "notes", created["id"])
        assert fetched["data"]["text"] == "hello"

    def test_update_item(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        created = appdb.create_item(
            app_id, "todos", {"title": "Buy milk", "done": False}
        )
        updated = appdb.update_item(
            app_id, "todos", created["id"], {"title": "Buy milk", "done": True}
        )
        assert updated["data"]["done"] is True
        assert updated["createdAt"] == created["createdAt"]
        assert updated["updatedAt"] >= created["updatedAt"]

    def test_delete_item(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        created = appdb.create_item(app_id, "todos", {"title": "Trash me"})
        appdb.delete_item(app_id, "todos", created["id"])

        with pytest.raises(appdb.NotFoundError):
            appdb.get_item(app_id, "todos", created["id"])

    def test_list_collections(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        appdb.create_item(app_id, "todos", {"x": 1})
        appdb.create_item(app_id, "notes", {"y": 2})
        appdb.create_item(app_id, "notes", {"y": 3})

        collections = appdb.list_collections(app_id)
        names = {c["name"] for c in collections}
        assert names == {"todos", "notes"}
        counts = {c["name"]: c["itemCount"] for c in collections}
        assert counts["todos"] == 1
        assert counts["notes"] == 2

    def test_drop_collection(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        appdb.create_item(app_id, "temp", {"x": 1})
        appdb.drop_collection(app_id, "temp")

        collections = appdb.list_collections(app_id)
        assert len(collections) == 0

    def test_invalid_collection_name(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        with pytest.raises(appdb.ValidationError):
            appdb.create_item(app_id, "123bad", {"x": 1})
        with pytest.raises(appdb.ValidationError):
            appdb.create_item(app_id, "DROP TABLE foo;--", {"x": 1})
        with pytest.raises(appdb.ValidationError):
            appdb.create_item(app_id, "", {"x": 1})

    def test_reserved_name_rejected(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        with pytest.raises(appdb.ValidationError):
            appdb.create_item(app_id, "select", {"x": 1})

    def test_max_collections_limit(self, app_with_owner):
        from app import appdb, config

        _, app_id = app_with_owner
        original = config.APPDB_MAX_COLLECTIONS
        config.APPDB_MAX_COLLECTIONS = 3
        try:
            appdb.create_item(app_id, "col_a", {"x": 1})
            appdb.create_item(app_id, "col_b", {"x": 1})
            appdb.create_item(app_id, "col_c", {"x": 1})
            with pytest.raises(appdb.ResourceLimitError):
                appdb.create_item(app_id, "col_d", {"x": 1})
        finally:
            config.APPDB_MAX_COLLECTIONS = original

    def test_max_items_limit(self, app_with_owner):
        from app import appdb, config

        _, app_id = app_with_owner
        original = config.APPDB_MAX_ITEMS
        config.APPDB_MAX_ITEMS = 5
        try:
            for i in range(5):
                appdb.create_item(app_id, "things", {"i": i})
            with pytest.raises(appdb.ResourceLimitError):
                appdb.create_item(app_id, "things", {"i": 999})
        finally:
            config.APPDB_MAX_ITEMS = original

    def test_item_too_large(self, app_with_owner):
        from app import appdb, config

        _, app_id = app_with_owner
        original = config.APPDB_MAX_ITEM_SIZE_BYTES
        config.APPDB_MAX_ITEM_SIZE_BYTES = 100
        try:
            with pytest.raises(appdb.ResourceLimitError):
                appdb.create_item(app_id, "big", {"payload": "x" * 200})
        finally:
            config.APPDB_MAX_ITEM_SIZE_BYTES = original

    def test_not_found_errors(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        with pytest.raises(appdb.NotFoundError):
            appdb.get_item(app_id, "nonexistent", "abc")
        with pytest.raises(appdb.NotFoundError):
            appdb.delete_item(app_id, "nonexistent", "abc")
        with pytest.raises(appdb.NotFoundError):
            appdb.drop_collection(app_id, "nonexistent")

    def test_pagination(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        for i in range(10):
            appdb.create_item(app_id, "pages", {"i": i})

        result = appdb.list_items(app_id, "pages", limit=3, offset=0)
        assert len(result["items"]) == 3
        assert result["total"] == 10

        result2 = appdb.list_items(app_id, "pages", limit=3, offset=3)
        assert len(result2["items"]) == 3
        # Ensure different items
        ids1 = {item["id"] for item in result["items"]}
        ids2 = {item["id"] for item in result2["items"]}
        assert ids1.isdisjoint(ids2)

    def test_filter(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        appdb.create_item(app_id, "tasks", {"status": "done", "text": "a"})
        appdb.create_item(app_id, "tasks", {"status": "pending", "text": "b"})
        appdb.create_item(app_id, "tasks", {"status": "done", "text": "c"})

        result = appdb.list_items(app_id, "tasks", filters={"status": "done"})
        assert result["total"] == 2
        assert all(item["data"]["status"] == "done" for item in result["items"])

    def test_nonexistent_collection_returns_empty(self, app_with_owner):
        from app import appdb

        _, app_id = app_with_owner
        result = appdb.list_items(app_id, "ghost")
        assert result["items"] == []
        assert result["total"] == 0


# ---- Integration tests for API routes ----


class TestAppDBRoutes:
    def test_create_and_list(self, client, app_with_owner):
        headers, app_id = app_with_owner

        resp = client.post(
            f"/v1/apps/{app_id}/db/todos",
            json={"data": {"title": "Test todo"}},
            headers=headers,
        )
        assert resp.status_code == 201
        item = resp.json()
        assert item["data"]["title"] == "Test todo"
        assert "id" in item

        resp = client.get(f"/v1/apps/{app_id}/db/todos", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1

    def test_get_update_delete(self, client, app_with_owner):
        headers, app_id = app_with_owner

        # Create
        resp = client.post(
            f"/v1/apps/{app_id}/db/items",
            json={"data": {"name": "widget"}},
            headers=headers,
        )
        item_id = resp.json()["id"]

        # Get
        resp = client.get(
            f"/v1/apps/{app_id}/db/items/{item_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "widget"

        # Update
        resp = client.put(
            f"/v1/apps/{app_id}/db/items/{item_id}",
            json={"data": {"name": "updated widget"}},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["name"] == "updated widget"

        # Delete
        resp = client.delete(
            f"/v1/apps/{app_id}/db/items/{item_id}",
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "deleted"

        # Confirm gone
        resp = client.get(
            f"/v1/apps/{app_id}/db/items/{item_id}",
            headers=headers,
        )
        assert resp.status_code == 404

    def test_list_collections(self, client, app_with_owner):
        headers, app_id = app_with_owner
        client.post(
            f"/v1/apps/{app_id}/db/alpha",
            json={"data": {"x": 1}},
            headers=headers,
        )
        client.post(
            f"/v1/apps/{app_id}/db/beta",
            json={"data": {"x": 2}},
            headers=headers,
        )

        resp = client.get(f"/v1/apps/{app_id}/db/collections", headers=headers)
        assert resp.status_code == 200
        names = {c["name"] for c in resp.json()["collections"]}
        assert names == {"alpha", "beta"}

    def test_drop_collection(self, client, app_with_owner):
        headers, app_id = app_with_owner
        client.post(
            f"/v1/apps/{app_id}/db/temp",
            json={"data": {"x": 1}},
            headers=headers,
        )
        resp = client.delete(f"/v1/apps/{app_id}/db/temp", headers=headers)
        assert resp.status_code == 200

        resp = client.get(f"/v1/apps/{app_id}/db/collections", headers=headers)
        assert len(resp.json()["collections"]) == 0

    def test_no_auth_returns_401(self, client, app_with_owner):
        _, app_id = app_with_owner
        resp = client.get(f"/v1/apps/{app_id}/db/collections")
        assert resp.status_code in (401, 403)

    def test_wrong_user_returns_403(self, client, app_with_owner):
        _, app_id = app_with_owner

        # Register a second user
        resp = client.post(
            "/v1/auth/register",
            json={"email": "other@example.com", "password": "password123"},
        )
        other_token = resp.json()["accessToken"]
        other_headers = {"Authorization": f"Bearer {other_token}"}

        resp = client.get(f"/v1/apps/{app_id}/db/collections", headers=other_headers)
        assert resp.status_code == 403

    def test_app_without_owner_returns_403(self, client, authed_user):
        from app.store import store

        headers, _ = authed_user
        # Create app without owner
        app_record = store.create_app(owner_id=None)
        app_id = app_record["appId"]

        resp = client.get(f"/v1/apps/{app_id}/db/collections", headers=headers)
        assert resp.status_code == 403

    def test_invalid_collection_name_returns_400(self, client, app_with_owner):
        headers, app_id = app_with_owner
        resp = client.post(
            f"/v1/apps/{app_id}/db/123invalid",
            json={"data": {"x": 1}},
            headers=headers,
        )
        assert resp.status_code == 400

    def test_nonexistent_app_returns_404(self, client, authed_user):
        headers, _ = authed_user
        resp = client.get(
            "/v1/apps/app_0000000000000000/db/collections",
            headers=headers,
        )
        assert resp.status_code == 404


# ---- End-to-end tests: generation → placeholder injection → DB usage ----

# Simulated HTML that a real LLM would generate, containing the AppDB helper
# with {{BACKEND_URL}} and {{APP_ID}} placeholders
MOCK_GENERATED_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Todo App</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  body { background: #0e0f12; color: #f4f7ff; font-family: sans-serif; padding: 16px; }
  .card { background: #1a1d24; border-radius: 12px; padding: 16px; margin-bottom: 12px; }
  button { background: #3bd6c6; color: #0e0f12; border: none; padding: 8px 16px; border-radius: 8px; }
  input { background: #1a1d24; color: #f4f7ff; border: 1px solid #3bd6c6; padding: 8px; border-radius: 8px; width: 100%; }
</style>
</head>
<body>
<h1>Todo App</h1>
<div class="card">
  <input id="todo-input" placeholder="What needs to be done?">
  <button onclick="addTodo()">Add</button>
</div>
<div id="todo-list"></div>
<script>
const AppDB = {
  _base: '{{BACKEND_URL}}/v1/apps/{{APP_ID}}/db',
  _token: localStorage.getItem('pluto_token'),
  _headers() {
    const h = {'Content-Type': 'application/json'};
    if (this._token) h['Authorization'] = 'Bearer ' + this._token;
    return h;
  },
  async list(collection, params) {
    const qs = params ? new URLSearchParams(params).toString() : '';
    const r = await fetch(this._base + '/' + collection + (qs ? '?' + qs : ''), {headers: this._headers()});
    if (!r.ok) throw new Error('AppDB list failed: ' + r.status);
    return (await r.json()).items;
  },
  async create(collection, data) {
    const r = await fetch(this._base + '/' + collection, {
      method: 'POST', headers: this._headers(), body: JSON.stringify({data})
    });
    if (!r.ok) throw new Error('AppDB create failed: ' + r.status);
    return r.json();
  },
  async delete(collection, id) {
    const r = await fetch(this._base + '/' + collection + '/' + id, {
      method: 'DELETE', headers: this._headers()
    });
    if (!r.ok) throw new Error('AppDB delete failed: ' + r.status);
    return r.json();
  }
};

async function addTodo() {
  const input = document.getElementById('todo-input');
  const title = input.value.trim();
  if (!title) return;
  await AppDB.create('todos', {title, done: false});
  input.value = '';
  loadTodos();
}

async function loadTodos() {
  const items = await AppDB.list('todos');
  const list = document.getElementById('todo-list');
  list.innerHTML = items.map(i =>
    `<div class="card">${i.data.title}</div>`
  ).join('');
}

loadTodos();
</script>
</body>
</html>"""

MOCK_BLUEPRINT = {
    "display_name": "Todo App",
    "package_name": "com.pluto.generated.todoapp",
    "features": ["add todos", "list todos", "delete todos"],
    "ui": "dark modern cards",
    "screens": ["main"],
    "data_models": ["todo: title, done"],
    "notes": "Uses AppDB for cloud persistence",
}


class TestEndToEnd:
    """End-to-end tests verifying the full generation → DB usage pipeline."""

    def test_inject_app_backend_url_replaces_placeholders(self):
        """Test that _inject_app_backend_url correctly substitutes placeholders."""
        from app import config
        from app.generator import _inject_app_backend_url

        config.PUBLIC_BASE_URL = "https://pluto.railway.app"

        result = _inject_app_backend_url(MOCK_GENERATED_HTML, "app_abc123def456789a")

        assert "{{BACKEND_URL}}" not in result
        assert "{{APP_ID}}" not in result
        assert "https://pluto.railway.app/v1/apps/app_abc123def456789a/db" in result

    def test_prompts_contain_appdb_helper(self):
        """Verify the LLM system prompts actually include the AppDB instructions."""
        from app.generator import APP_GEN_SYSTEM_PROMPT, EDIT_HTML_SYSTEM_PROMPT

        for prompt in [APP_GEN_SYSTEM_PROMPT, EDIT_HTML_SYSTEM_PROMPT]:
            assert "AppDB" in prompt
            assert "{{BACKEND_URL}}" in prompt
            assert "{{APP_ID}}" in prompt
            assert "async list(" in prompt
            assert "async create(" in prompt
            assert "async update(" in prompt
            assert "async delete(" in prompt
            assert "localStorage" in prompt

    def test_generation_job_injects_placeholders(self):
        """Mock the OpenAI client and run a full generation job, verifying
        that the output HTML has placeholders replaced with real values."""
        from app import config
        from app.generator import run_generation_job
        from app.store import store

        config.PUBLIC_BASE_URL = "https://pluto.test"

        # Create an app and job
        app_record = store.create_app(owner_id="usr_test1234567890ab")
        app_id = app_record["appId"]
        job_record = store.create_job(
            app_id=app_id,
            request={
                "prompt": "todo list app with cloud sync",
                "inputImages": [],
            },
        )
        job_id = job_record["jobId"]

        # Mock OpenAI to return blueprint JSON first, then the HTML
        mock_client = MagicMock()
        blueprint_response = MagicMock()
        blueprint_response.output_text = (
            '{"display_name":"Todo App","package_name":"com.pluto.generated.todoapp",'
            '"features":["add todos"],"ui":"dark","screens":["main"],'
            '"data_models":["todo"],"notes":"uses AppDB"}'
        )
        html_response = MagicMock()
        html_response.output_text = MOCK_GENERATED_HTML

        # First call = blueprint, second call = HTML
        mock_client.responses.create.side_effect = [blueprint_response, html_response]

        with patch("app.generator.OpenAI", return_value=mock_client):
            run_generation_job(store, job_id)

        # Verify job succeeded
        job = store.get_job(job_id)
        assert job["status"] == "SUCCEEDED", f"Job failed: {job.get('error')}"

        # Verify the artifact exists and contains injected HTML
        version_id = job["resultVersionId"]
        version = store.get_version(version_id)
        assert version is not None

        artifact_id = version["artifactIds"][0]
        artifact = store.get_artifact(artifact_id)
        zip_path = artifact["path"]

        # Extract and check the HTML in the zip
        with ZipFile(zip_path, "r") as zf:
            html = zf.read("index.html").decode("utf-8")

        # The key assertion: placeholders must be replaced
        assert "{{BACKEND_URL}}" not in html
        assert "{{APP_ID}}" not in html
        assert f"https://pluto.test/v1/apps/{app_id}/db" in html

    def test_generated_app_can_use_db_endpoints(self, client, authed_user):
        """Simulate what a generated app would do: use the DB endpoints
        to create, list, update, and delete items — the full CRUD loop
        that the AppDB JS helper performs via fetch()."""
        from app.store import store

        headers, user_id = authed_user
        app_record = store.create_app(owner_id=user_id)
        app_id = app_record["appId"]
        base = f"/v1/apps/{app_id}/db"

        # -- Simulating what the generated JS does via AppDB.create() --
        resp = client.post(
            f"{base}/todos",
            json={"data": {"title": "Buy groceries", "done": False}},
            headers=headers,
        )
        assert resp.status_code == 201
        todo1 = resp.json()
        assert todo1["data"]["title"] == "Buy groceries"
        todo1_id = todo1["id"]

        resp = client.post(
            f"{base}/todos",
            json={"data": {"title": "Walk the dog", "done": False}},
            headers=headers,
        )
        assert resp.status_code == 201
        todo2_id = resp.json()["id"]

        # -- AppDB.list('todos') --
        resp = client.get(f"{base}/todos", headers=headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 2

        # -- AppDB.list('todos', {filter.title: 'Buy groceries'}) --
        resp = client.get(f"{base}/todos?filter.title=Buy groceries", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["data"]["title"] == "Buy groceries"

        # -- AppDB.update() to mark a todo done --
        resp = client.put(
            f"{base}/todos/{todo1_id}",
            json={"data": {"title": "Buy groceries", "done": True}},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["data"]["done"] is True

        # -- AppDB.get() to verify --
        resp = client.get(f"{base}/todos/{todo1_id}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["data"]["done"] is True

        # -- AppDB.delete() --
        resp = client.delete(f"{base}/todos/{todo2_id}", headers=headers)
        assert resp.status_code == 200

        # Verify only 1 todo remains
        resp = client.get(f"{base}/todos", headers=headers)
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["id"] == todo1_id

        # -- Verify collections endpoint shows 'todos' --
        resp = client.get(f"{base}/collections", headers=headers)
        assert resp.status_code == 200
        collections = resp.json()["collections"]
        assert len(collections) == 1
        assert collections[0]["name"] == "todos"
        assert collections[0]["itemCount"] == 1

    def test_two_apps_have_isolated_databases(self, client, authed_user):
        """Verify that two different apps owned by the same user have
        completely separate databases — data in app A is not visible in app B."""
        from app.store import store

        headers, user_id = authed_user

        app_a = store.create_app(owner_id=user_id)
        app_b = store.create_app(owner_id=user_id)
        app_a_id = app_a["appId"]
        app_b_id = app_b["appId"]

        # Write to app A
        resp = client.post(
            f"/v1/apps/{app_a_id}/db/scores",
            json={"data": {"player": "Alice", "score": 100}},
            headers=headers,
        )
        assert resp.status_code == 201

        # App B should have empty collections
        resp = client.get(f"/v1/apps/{app_b_id}/db/collections", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["collections"] == []

        # App B's scores collection should be empty
        resp = client.get(f"/v1/apps/{app_b_id}/db/scores", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

        # Write to app B
        resp = client.post(
            f"/v1/apps/{app_b_id}/db/scores",
            json={"data": {"player": "Bob", "score": 200}},
            headers=headers,
        )
        assert resp.status_code == 201

        # Verify each app sees only its own data
        resp = client.get(f"/v1/apps/{app_a_id}/db/scores", headers=headers)
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["data"]["player"] == "Alice"

        resp = client.get(f"/v1/apps/{app_b_id}/db/scores", headers=headers)
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["data"]["player"] == "Bob"

    def test_edit_flow_also_injects_placeholders(self):
        """Verify that the edit flow (existing app modification) also
        replaces {{BACKEND_URL}} and {{APP_ID}} in the output."""
        from app import config
        from app.generator import run_generation_job
        from app.store import store

        config.PUBLIC_BASE_URL = "https://pluto.test"

        app_record = store.create_app(owner_id="usr_test1234567890ab")
        app_id = app_record["appId"]

        # Simulate an edit request with existing HTML
        existing_html = "<html><body>Old app</body></html>"
        job_record = store.create_job(
            app_id=app_id,
            request={
                "prompt": "add a leaderboard feature",
                "inputImages": [],
                "baseTemplate": existing_html,
            },
        )
        job_id = job_record["jobId"]

        # Mock: edit blueprint response, then edited HTML response
        mock_client = MagicMock()
        edit_blueprint_response = MagicMock()
        edit_blueprint_response.output_text = (
            '{"display_name":"Todo App","package_name":"com.pluto.generated.todoapp",'
            '"features":["add todos","leaderboard"],"ui":"dark","screens":["main","leaderboard"],'
            '"data_models":["todo","score"],"notes":"added leaderboard with AppDB"}'
        )
        edited_html_response = MagicMock()
        edited_html_response.output_text = MOCK_GENERATED_HTML

        mock_client.responses.create.side_effect = [
            edit_blueprint_response,
            edited_html_response,
        ]

        with patch("app.generator.OpenAI", return_value=mock_client):
            run_generation_job(store, job_id)

        job = store.get_job(job_id)
        assert job["status"] == "SUCCEEDED", f"Job failed: {job.get('error')}"

        version = store.get_version(job["resultVersionId"])
        artifact = store.get_artifact(version["artifactIds"][0])

        with ZipFile(artifact["path"], "r") as zf:
            html = zf.read("index.html").decode("utf-8")

        assert "{{BACKEND_URL}}" not in html
        assert "{{APP_ID}}" not in html
        assert f"https://pluto.test/v1/apps/{app_id}/db" in html
