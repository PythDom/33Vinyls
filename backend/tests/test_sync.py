import uuid

from fastapi.testclient import TestClient

from vinyls.main import app


def op(release_id, kind="collection", updated="2026-11-12T10:00:00+00:00", **fields):
    return {"id": str(uuid.uuid4()), "release_id": release_id, "kind": kind, "fields": fields, "updated_at": updated}


def test_push_then_pull(admin):
    a = op(100101, media_grade="VG+", notes="Shelf 2", location="Shelf 2")
    b = op(100204, kind="want", max_price=40)
    r = admin.post("/api/sync", json={"ops": [a, b]}).json()
    assert sorted(r["applied"]) == sorted([a["id"], b["id"]])
    pulled = admin.get("/api/sync?since=0").json()
    assert {i["id"] for i in pulled["items"]} == {a["id"], b["id"]}
    assert {rel["id"] for rel in pulled["releases"]} == {100101, 100204}
    assert pulled["cursor"] > 0
    assert admin.get(f"/api/sync?since={pulled['cursor']}").json()["items"] == []


def test_last_writer_wins(admin):
    a = op(100101, updated="2026-11-12T10:00:00+00:00", notes="new")
    admin.post("/api/sync", json={"ops": [a]})
    older = {**a, "updated_at": "2026-11-11T10:00:00+00:00", "fields": {"notes": "old"}}
    assert admin.post("/api/sync", json={"ops": [older]}).json()["skipped"] == [a["id"]]
    newer = {**a, "updated_at": "2026-11-12T11:00:00+00:00", "deleted": True}
    assert admin.post("/api/sync", json={"ops": [newer]}).json()["applied"] == [a["id"]]
    items = admin.get("/api/sync?since=0").json()["items"]
    assert items[0]["deleted"] is True and items[0]["fields"]["notes"] == "new"


def test_users_are_isolated(admin):
    admin.post("/api/sync", json={"ops": [op(100101)]})
    code = admin.post("/api/invites").json()["code"]
    friend = TestClient(app)
    friend.post("/api/register", json={"username": "alex", "password": "password123", "invite": code})
    assert friend.get("/api/sync?since=0").json()["items"] == []
    mine = admin.get("/api/sync?since=0").json()["items"][0]
    hijack = {**mine, "updated_at": "2030-01-01T00:00:00+00:00", "fields": {"notes": "mine now"}}
    hijack.pop("seq")
    assert friend.post("/api/sync", json={"ops": [hijack]}).json()["skipped"] == [mine["id"]]


def test_unknown_fields_dropped(admin):
    a = op(100101, notes="ok", is_admin=True)
    admin.post("/api/sync", json={"ops": [a]})
    assert admin.get("/api/sync?since=0").json()["items"][0]["fields"] == {"notes": "ok"}
