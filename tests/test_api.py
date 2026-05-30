"""Tests for the FastAPI layer (storyplanner.api)."""

from __future__ import annotations

import warnings

import pytest

warnings.filterwarnings("ignore")

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from storyplanner.api.app import create_api  # noqa: E402
from storyplanner.api.config import ApiConfig  # noqa: E402
from storyplanner.db import Database  # noqa: E402


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Keep assistant-settings tests from touching the real settings file."""
    import storyplanner.settings as settings

    settings._instance = None
    monkeypatch.setattr(settings, "CONFIG_DIR", tmp_path, raising=False)
    monkeypatch.setattr(settings, "SETTINGS_FILE", tmp_path / "settings.json", raising=False)
    yield
    settings._instance = None


@pytest.fixture
def env():
    db = Database()
    project = db.create_project("API Project", narrative_engine="novel")
    db.create_character(project.id, "Alice")
    app = create_api(db=db, config=ApiConfig(mode="desktop"))
    client = TestClient(app)
    return client, db, project.id


# -- Health & projects -------------------------------------------------------


def test_health(env):
    client, _, _ = env
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["mode"] == "desktop"


def test_list_projects(env):
    client, _, pid = env
    r = client.get("/api/projects")
    assert r.status_code == 200
    assert any(p["id"] == pid for p in r.json())


def test_create_project(env):
    client, _, _ = env
    r = client.post(
        "/api/projects",
        json={"title": "Fresh", "narrative_engine": "screenplay"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Fresh"
    assert body["narrative_engine"] == "screenplay"


def test_get_project_and_404(env):
    client, _, pid = env
    assert client.get(f"/api/projects/{pid}").json()["id"] == pid
    assert client.get("/api/projects/99999").status_code == 404


def test_project_lifecycle_endpoints(env):
    client, _, pid = env
    assert client.post(f"/api/projects/{pid}/open").status_code == 200
    assert client.post(f"/api/projects/{pid}/save").json()["ok"] is True
    assert client.post(f"/api/projects/{pid}/close").json()["ok"] is True


def test_delete_project_not_supported(env):
    client, _, pid = env
    assert client.delete(f"/api/projects/{pid}").status_code == 501


def test_project_settings_roundtrip(env):
    client, _, pid = env
    assert client.get(f"/api/projects/{pid}/settings").json()["settings"] == {}
    r = client.patch(
        f"/api/projects/{pid}/settings", json={"settings": {"theme": "dark"}},
    )
    assert r.json()["settings"]["theme"] == "dark"
    # Persisted.
    assert client.get(f"/api/projects/{pid}/settings").json()["settings"]["theme"] == "dark"


# -- Scenes ------------------------------------------------------------------


def test_scene_crud(env):
    client, _, pid = env
    # Create
    r = client.post(
        f"/api/projects/{pid}/scenes",
        json={"title": "Opening", "summary": "It begins", "plotline": "Main"},
    )
    assert r.status_code == 201
    sid = r.json()["id"]
    # List
    assert any(s["id"] == sid for s in client.get(f"/api/projects/{pid}/scenes").json())
    # Get
    assert client.get(f"/api/projects/{pid}/scenes/{sid}").json()["title"] == "Opening"
    # Patch (must not clobber summary)
    client.patch(f"/api/projects/{pid}/scenes/{sid}", json={"beat": "inciting"})
    scene = client.get(f"/api/projects/{pid}/scenes/{sid}").json()
    assert scene["summary"] == "It begins"
    assert scene["beat"] == "inciting"
    # Delete
    assert client.delete(f"/api/projects/{pid}/scenes/{sid}").json()["ok"] is True
    assert client.get(f"/api/projects/{pid}/scenes/{sid}").status_code == 404


def test_scene_unsaved_changes_visible_immediately(env):
    """A mutation is reflected by the very next read (single source of truth)."""
    client, db, pid = env
    sid = client.post(f"/api/projects/{pid}/scenes", json={"title": "X"}).json()["id"]
    client.patch(f"/api/projects/{pid}/scenes/{sid}", json={"title": "Renamed"})
    assert db.get_scene_by_id(sid).title == "Renamed"


def test_scene_patch_preserves_associations(env):
    """A partial PATCH must not wipe character/place links or states."""
    client, db, pid = env
    alice = db.create_character(pid, "Alice")
    castle = db.create_place(pid, "Castle")
    sid = client.post(
        f"/api/projects/{pid}/scenes",
        json={"title": "S", "character_ids": [alice.id], "place_ids": [castle.id]},
    ).json()["id"]
    client.patch(f"/api/projects/{pid}/scenes/{sid}", json={"beat": "inciting"})
    scene = client.get(f"/api/projects/{pid}/scenes/{sid}").json()
    assert scene["character_ids"] == [alice.id]
    assert scene["place_ids"] == [castle.id]


# -- Outline / Plot / Timeline -----------------------------------------------


def test_outline_crud(env):
    client, _, pid = env
    root = client.post(f"/api/projects/{pid}/outline/nodes", json={"title": "Act I"}).json()
    child = client.post(
        f"/api/projects/{pid}/outline/nodes",
        json={"title": "Ch 1", "parent_id": root["id"]},
    ).json()
    tree = client.get(f"/api/projects/{pid}/outline").json()
    assert tree[0]["title"] == "Act I"
    assert tree[0]["children"][0]["title"] == "Ch 1"
    client.patch(
        f"/api/projects/{pid}/outline/nodes/{child['id']}", json={"title": "Chapter One"},
    )
    assert client.get(f"/api/projects/{pid}/outline").json()[0]["children"][0]["title"] == "Chapter One"
    assert client.delete(f"/api/projects/{pid}/outline/nodes/{child['id']}").json()["ok"]


def test_plot_blocks_and_rename(env):
    client, _, pid = env
    client.post(f"/api/projects/{pid}/scenes", json={"title": "S1", "plotline": "Main"})
    blocks = client.get(f"/api/projects/{pid}/plot").json()
    assert blocks[0]["plotline"] == "Main"
    renamed = client.patch(
        f"/api/projects/{pid}/plot/blocks/Main", json={"plotline": "A-Plot"},
    )
    assert renamed.json()["plotline"] == "A-Plot"


def test_timeline_create_and_update(env):
    client, _, pid = env
    ev = client.post(
        f"/api/projects/{pid}/timeline/events",
        json={"title": "Dawn", "time_of_day": "DAY", "duration_minutes": 5},
    ).json()
    assert ev["time_of_day"] == "DAY"
    assert ev["duration_minutes"] == 5
    upd = client.patch(
        f"/api/projects/{pid}/timeline/events/{ev['id']}",
        json={"location": "Castle"},
    ).json()
    assert upd["location"] == "Castle"


# -- PSYKE -------------------------------------------------------------------


def test_psyke_entry_crud(env):
    client, _, pid = env
    e = client.post(
        f"/api/projects/{pid}/psyke/entries",
        json={"name": "Justice", "type": "theme", "aliases": ["Law"]},
    ).json()
    eid = e["id"]
    assert e["type"] == "theme"
    assert e["aliases"] == ["Law"]
    client.patch(f"/api/projects/{pid}/psyke/entries/{eid}", json={"notes": "core"})
    assert client.get(f"/api/projects/{pid}/psyke/entries/{eid}").json()["notes"] == "core"
    assert client.delete(f"/api/projects/{pid}/psyke/entries/{eid}").json()["ok"]


def test_psyke_relations(env):
    client, _, pid = env
    a = client.post(f"/api/projects/{pid}/psyke/entries", json={"name": "Hero"}).json()
    b = client.post(f"/api/projects/{pid}/psyke/entries", json={"name": "Theme", "type": "theme"}).json()
    rel = client.post(
        f"/api/projects/{pid}/psyke/relations",
        json={"source_id": a["id"], "target_id": b["id"], "relation_type": "thematic_echo"},
    ).json()
    assert rel["relation_type"] == "thematic_echo"
    rels = client.get(f"/api/projects/{pid}/psyke/relations").json()
    assert len(rels) == 1
    assert client.delete(f"/api/projects/{pid}/psyke/relations/{rel['id']}").json()["ok"]
    assert client.get(f"/api/projects/{pid}/psyke/relations").json() == []


def test_relation_delete_rejects_cross_project_target(env):
    """Deleting a relation must validate both endpoints belong to the project."""
    client, db, pid = env
    a = client.post(f"/api/projects/{pid}/psyke/entries", json={"name": "Hero"}).json()
    other_pid = db.create_project("Other").id
    foreign = db.create_psyke_entry(other_pid, "Foreign", entry_type="theme")
    r = client.delete(f"/api/projects/{pid}/psyke/relations/{a['id']}:{foreign.id}")
    assert r.status_code == 404


def test_psyke_progressions_and_search(env):
    client, _, pid = env
    e = client.post(f"/api/projects/{pid}/psyke/entries", json={"name": "Hero"}).json()
    prog = client.post(
        f"/api/projects/{pid}/psyke/progressions",
        json={"entry_id": e["id"], "text": "grows up"},
    ).json()
    assert prog["text"] == "grows up"
    found = client.get(f"/api/projects/{pid}/psyke/search", params={"q": "hero"}).json()
    assert any(x["name"] == "Hero" for x in found)


# -- Notes -------------------------------------------------------------------


def test_note_crud(env):
    client, _, pid = env
    n = client.post(
        f"/api/projects/{pid}/notes",
        json={"title": "Idea", "content": "body", "tags": ["draft"]},
    ).json()
    nid = n["id"]
    assert n["tags"] == ["draft"]
    client.patch(f"/api/projects/{pid}/notes/{nid}", json={"pinned": True})
    assert client.get(f"/api/projects/{pid}/notes").json()[0]["pinned"] is True
    assert client.delete(f"/api/projects/{pid}/notes/{nid}").json()["ok"]


# -- Assistant / Connector ---------------------------------------------------


def test_assistant_chat_mocked(env, monkeypatch):
    client, _, pid = env
    from storyplanner import assistant

    monkeypatch.setattr(
        assistant, "chat_completion", lambda *a, **k: ("Mocked reply", False),
    )
    r = client.post(
        f"/api/projects/{pid}/assistant/chat", json={"message": "hello"},
    )
    assert r.status_code == 200
    assert r.json() == {"reply": "Mocked reply", "cached": False}


def test_assistant_settings_roundtrip(env):
    client, _, pid = env
    client.patch(
        f"/api/projects/{pid}/assistant/settings",
        json={"provider": "OpenAI", "model": "gpt-4o", "api_key": "secret"},
    )
    got = client.get(f"/api/projects/{pid}/assistant/settings").json()
    assert got["provider"] == "OpenAI"
    assert got["model"] == "gpt-4o"
    assert got["api_key"] is None  # never returned


def test_connector_actions_listed(env):
    client, _, pid = env
    actions = client.get(f"/api/projects/{pid}/connector/actions").json()
    names = {a["name"] for a in actions}
    assert "get_project" in names
    assert all("category" in a for a in actions)


def test_connector_execute_validates_unknown_action(env):
    client, _, pid = env
    r = client.post(
        f"/api/projects/{pid}/connector/execute", json={"action": "does_not_exist"},
    )
    body = r.json()
    assert body["ok"] is False
    assert "Unknown action" in body["error"]


def test_connector_read_action_allowed(env):
    client, _, pid = env
    r = client.post(
        f"/api/projects/{pid}/connector/execute", json={"action": "get_project"},
    )
    body = r.json()
    assert body["ok"] is True
    assert body["result"]["id"] == pid


def test_assistant_action_uses_safe_layer(env):
    client, _, pid = env
    # Write action is gated by connector settings (disabled by default) → the
    # safe layer refuses rather than performing a raw mutation.
    r = client.post(
        f"/api/projects/{pid}/assistant/action",
        json={"action": "create_scene", "args": {"title": "Forced"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False  # connector disabled by default
    assert "disabled" in body["error"].lower()


# -- Export ------------------------------------------------------------------


def test_export_json(env):
    client, _, pid = env
    client.post(f"/api/projects/{pid}/scenes", json={"title": "S1", "plotline": "Main"})
    r = client.post(
        f"/api/projects/{pid}/export",
        json={"export_type": "story_elements", "format": "json"},
    )
    payload = r.json()["payload"]
    assert payload["export_type"] == "story_elements"
    assert "plot" in payload


def test_export_markdown_and_csv(env):
    client, _, pid = env
    client.post(f"/api/projects/{pid}/psyke/entries", json={"name": "Justice", "type": "theme"})
    md = client.post(
        f"/api/projects/{pid}/export",
        json={"export_type": "psyke_data", "format": "markdown"},
    ).json()
    assert md["content"] and "#" in md["content"]
    csv = client.post(
        f"/api/projects/{pid}/export",
        json={"export_type": "psyke_data", "format": "csv"},
    ).json()
    assert isinstance(csv["files"], dict) and csv["files"]


def test_export_bad_request(env):
    client, _, pid = env
    r = client.post(
        f"/api/projects/{pid}/export", json={"export_type": "nope", "format": "json"},
    )
    assert r.status_code == 400


# -- Events ------------------------------------------------------------------


def test_events_poll_captures_mutations(env):
    client, _, pid = env
    before = client.get(f"/api/projects/{pid}/events/poll").json()["cursor"]
    client.post(f"/api/projects/{pid}/scenes", json={"title": "Boom"})
    after = client.get(f"/api/projects/{pid}/events/poll", params={"since": before}).json()
    event_names = {e["event"] for e in after["events"]}
    assert "scene_changed" in event_names or "scenes_changed" in event_names
    assert after["cursor"] > before


def test_events_sse_stream_connects(env):
    client, _, pid = env
    # Use the finite "drain" mode so the test never blocks on the live tail.
    r = client.get(f"/api/projects/{pid}/events", params={"once": True})
    assert r.status_code == 200
    assert "text/event-stream" in r.headers["content-type"]
    assert "event: connected" in r.text


def test_events_sse_drains_buffered_events(env):
    client, _, pid = env
    client.post(f"/api/projects/{pid}/notes", json={"title": "N"})
    body = client.get(f"/api/projects/{pid}/events", params={"once": True}).text
    assert "connected" in body


# -- Auth hook ---------------------------------------------------------------


def test_auth_hook_enforced_when_token_set():
    db = Database()
    db.create_project("Secured")
    app = create_api(db=db, config=ApiConfig(mode="remote", auth_token="s3cret"))
    client = TestClient(app)
    # Health is open; project routes require the token.
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/projects").status_code == 403
    ok = client.get("/api/projects", headers={"Authorization": "Bearer s3cret"})
    assert ok.status_code == 200
