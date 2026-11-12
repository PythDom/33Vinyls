import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("DISCOGS_MODE", "demo")
os.environ.setdefault("SECURE_COOKIES", "false")
os.environ.setdefault("VINYLS_STATIC_DIR", "/nonexistent")
os.environ.setdefault("BACKGROUND_JOBS", "false")

from fastapi.testclient import TestClient  # noqa: E402

from vinyls import db  # noqa: E402
from vinyls.config import settings  # noqa: E402
from vinyls.main import app  # noqa: E402


@pytest.fixture()
def client(tmp_path):
    settings.data_dir = tmp_path / "data"
    settings.sync_dir = tmp_path / "Sync"
    settings.sync_dir.mkdir()
    settings.discogs_mode = "demo"
    db.reset_connection()
    with TestClient(app) as c:
        yield c
    db.reset_connection()


@pytest.fixture()
def admin(client):
    r = client.post("/api/register", json={"username": "dom", "password": "correct horse"})
    assert r.status_code == 200, r.text
    return client


def make_friend(admin, username="alex"):
    code = admin.post("/api/invites").json()["code"]
    friend = TestClient(app)
    r = friend.post("/api/register", json={"username": username, "password": "password123", "invite": code})
    assert r.status_code == 200
    return friend
