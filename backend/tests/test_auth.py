from fastapi.testclient import TestClient

from vinyls.main import app


def test_first_user_becomes_admin_without_invite(client):
    assert client.get("/api/status").json()["needs_setup"] is True
    r = client.post("/api/register", json={"username": "dom", "password": "correct horse"})
    assert r.status_code == 200
    assert r.json()["is_admin"] is True
    assert client.get("/api/me").json()["username"] == "dom"


def test_second_user_needs_invite(admin):
    friend = TestClient(app)
    r = friend.post("/api/register", json={"username": "alex", "password": "password123"})
    assert r.status_code == 403
    code = admin.post("/api/invites").json()["code"]
    r = friend.post("/api/register", json={"username": "alex", "password": "password123", "invite": code})
    assert r.status_code == 200 and r.json()["is_admin"] is False
    # invite can't be reused
    r = TestClient(app).post("/api/register", json={"username": "sam", "password": "password123", "invite": code})
    assert r.status_code == 403
    # non-admins can't create invites
    assert friend.post("/api/invites").status_code == 403


def test_login_logout(admin):
    admin.post("/api/logout")
    assert admin.get("/api/me").status_code == 401
    assert admin.post("/api/login", json={"username": "dom", "password": "wrong password"}).status_code == 401
    assert admin.post("/api/login", json={"username": "DOM", "password": "correct horse"}).status_code == 200
    assert admin.get("/api/me").status_code == 200


def test_requires_login(client):
    assert client.get("/api/sync").status_code == 401
    assert client.get("/api/search?q=x").status_code == 401


def test_live_mode_requires_discogs_link(admin):
    from vinyls.config import settings
    settings.discogs_mode = "live"
    try:
        r = admin.get("/api/search?q=anything")
        assert r.status_code == 409
        assert "Discogs" in r.json()["detail"]
        assert admin.get("/api/me").json()["discogs"]["linked"] is False
    finally:
        settings.discogs_mode = "demo"
