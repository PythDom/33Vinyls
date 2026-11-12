import asyncio
import csv
import io
import sqlite3
import time
import uuid
from datetime import datetime, timedelta

from vinyls import backup, db, jobs
from vinyls.config import settings

from .conftest import make_friend


def wait_import(client):
    for _ in range(100):
        s = client.get("/api/discogs/import").json()
        if s["state"] != "running":
            return s
        time.sleep(0.05)
    raise AssertionError("import did not finish")


def add(client, release_id, kind="collection", **fields):
    op = {"id": str(uuid.uuid4()), "release_id": release_id, "kind": kind, "fields": fields, "updated_at": db.now()}
    assert client.post("/api/sync", json={"ops": [op]}).status_code == 200


# ---------------------------------------------------------------- Discogs import

def test_import_collection_and_wantlist(admin):
    assert admin.post("/api/discogs/import", json={}).json()["state"] == "running"
    s = wait_import(admin)
    assert s["state"] == "done" and s["added"] == 11, s
    items = admin.get("/api/sync?since=0").json()["items"]
    coll = [i for i in items if i["kind"] == "collection"]
    assert len(coll) == 8 and len([i for i in items if i["kind"] == "want"]) == 3
    first = next(i for i in coll if i["release_id"] == 100103)
    assert first["fields"]["media_grade"] == "VG+" and first["fields"]["sleeve_grade"] == "VG"
    assert first["fields"]["notes"] == "Bought at the Brussels record fair"
    # running it again adds nothing
    admin.post("/api/discogs/import", json={})
    again = wait_import(admin)
    assert again["added"] == 0 and again["skipped"] == 11


def test_imported_records_get_completed_in_background(admin):
    admin.post("/api/discogs/import", json={})
    wait_import(admin)
    release = next(r for r in admin.get("/api/sync?since=0").json()["releases"] if r["id"] == 100302)
    assert release.get("partial") and release["matrix"] == []
    cursor = admin.get("/api/sync?since=0").json()["cursor"]
    assert asyncio.run(jobs.enrich_batch(limit=50)) == 11
    changed = {r["id"]: r for r in admin.get(f"/api/sync?since={cursor}").json()["releases"]}
    assert changed[100302]["matrix"] == ["207114-A", "207114-B"] and not changed[100302].get("partial")


def test_background_price_refresh_and_stats(admin):
    add(admin, 100101, media_grade="VG+", purchase_price=100.0)
    add(admin, 100301, media_grade="NM")
    assert asyncio.run(jobs.refresh_prices_batch(limit=10)) == 2
    assert asyncio.run(jobs.refresh_prices_batch(limit=10)) == 0  # fresh now
    s = admin.get("/api/stats").json()
    assert s["records"] == 2 and s["total_value"] == 180.0 + 38.0
    assert s["total_paid"] == 100.0 and s["gain"] == 80.0
    assert s["top"][0]["title"] == "Neon Harbour"


# ---------------------------------------------------------------- exports & backups

def test_csv_download_is_excel_friendly(admin):
    add(admin, 100101, media_grade="VG+", purchase_price=12.5, notes="café; shelf 2")
    r = admin.get("/api/export/collection.csv")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    text = r.content.decode("utf-8")
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿")), delimiter=";"))
    assert rows[0][0] == "Artist" and rows[1][0] == "The Velvet Static"
    assert "12,50" in rows[1] and "café; shelf 2" in rows[1]


def test_export_writes_snapshot_and_files_without_secrets(admin):
    admin.post("/api/discogs/import", json={})
    wait_import(admin)
    db.run("INSERT INTO discogs_links(user_id, username, method, token_enc, linked_at) VALUES (1,'dom','token','secret',?)", (db.now(),))
    r = admin.post("/api/admin/backups/export").json()
    snap = settings.sync_dir / "db" / r["snapshot"]
    assert snap.exists()
    con = sqlite3.connect(snap)
    assert con.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 11
    assert con.execute("SELECT COUNT(*) FROM discogs_links").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 0
    con.close()
    folder = settings.sync_dir / "export" / "dom"
    assert {p.name for p in folder.iterdir()} == {"collection.csv", "wantlist.csv", "collection.json"}
    assert not list(settings.sync_dir.rglob(".tmp-*"))
    assert not (settings.sync_dir / "secret_key").exists()
    status = admin.get("/api/admin/backups").json()
    assert status["available"] and status["last_export_file"] == r["snapshot"] and status["changes_since_export"] == 0


def test_restore_saves_current_first_and_changes_generation(admin):
    add(admin, 100101)
    snap = admin.post("/api/admin/backups/export").json()["snapshot"]
    gen_before = admin.get("/api/sync?since=0").json()["generation"]
    add(admin, 100201)
    add(admin, 100301)
    assert len(admin.get("/api/sync?since=0").json()["items"]) == 3
    assert admin.post("/api/admin/backups/restore", json={"file": f"db/{snap}"}).status_code == 400  # no confirmation
    r = admin.post("/api/admin/backups/restore", json={"file": f"db/{snap}", "confirm": True})
    assert r.status_code == 200, r.text
    assert admin.get("/api/me").status_code == 200  # still signed in
    pulled = admin.get("/api/sync?since=0").json()
    assert len(pulled["items"]) == 1 and pulled["generation"] != gen_before
    assert list((settings.sync_dir / "db").glob("db-before-restore-*.sqlite3"))


def test_restore_rejects_other_files(admin):
    bad = settings.sync_dir / "restore" / "nope.sqlite3"
    bad.parent.mkdir(exist_ok=True)
    sqlite3.connect(bad).execute("CREATE TABLE x(y)").connection.commit()
    r = admin.post("/api/admin/backups/restore", json={"file": "restore/nope.sqlite3", "confirm": True})
    assert r.status_code == 400 and "not a 33Vinyls database" in r.json()["detail"]
    assert admin.post("/api/admin/backups/restore", json={"file": "../etc/passwd", "confirm": True}).status_code == 400


def test_backups_admin_only(admin):
    friend = make_friend(admin)
    assert friend.get("/api/admin/backups").status_code == 403
    assert friend.post("/api/admin/backups/export").status_code == 403


def test_prune_keeps_daily_weekly_monthly(tmp_path):
    today = datetime(2026, 11, 12, 12, 0)
    for days in range(0, 400):
        for hour in ("0300", "1500"):
            when = today - timedelta(days=days)
            (tmp_path / f"33vinyls-{when:%Y-%m-%d}T{hour}.sqlite3").write_text("x")
    (tmp_path / "db-before-restore-2020.sqlite3").write_text("keep me")
    backup.prune(tmp_path, today)
    kept = sorted(p.name for p in tmp_path.glob("33vinyls-*.sqlite3"))
    assert 14 <= len(kept) <= 14 + 8 + 13
    assert "33vinyls-2026-11-12T1500.sqlite3" in kept and "33vinyls-2026-11-12T0300.sqlite3" not in kept
    assert all(p.name >= "33vinyls-2025-10" for p in tmp_path.glob("33vinyls-*.sqlite3"))
    assert (tmp_path / "db-before-restore-2020.sqlite3").exists()


def test_export_schedule(admin):
    settings.nightly_export = "03:00"
    morning = datetime(2026, 11, 12, 2, 59).astimezone()
    assert backup.due_for_export(morning) is None
    assert backup.due_for_export(morning + timedelta(minutes=2)) == "nightly"
    admin.post("/api/admin/backups/export")
    assert backup.due_for_export(datetime.now().astimezone()) is None
    for n in range(25):
        add(admin, 100101 + (n % 3))
    assert backup.due_for_export(datetime.now().astimezone()) is None  # still busy
    assert backup.due_for_export(datetime.now().astimezone() + timedelta(minutes=11)) == "changes"


def test_export_unavailable_without_sync_folder(admin):
    settings.sync_dir = settings.data_dir / "missing"
    status = admin.get("/api/admin/backups").json()
    assert status["available"] is False and "not mounted" in status["problem"]
    assert admin.post("/api/admin/backups/export").status_code == 400
    assert jobs.export_if_due() is None


# ---------------------------------------------------------------- sharing

def test_sharing_is_opt_in_and_mutual(admin):
    friend = make_friend(admin)
    add(friend, 100101)
    add(friend, 100201, kind="want")
    # nothing shared by default
    assert admin.get("/api/releases/100101").json()["friends"] == []
    friend.put("/api/sharing", json={"share_collection": True, "share_wantlist": True, "share_values": False})
    # I don't share anything yet → I see nothing
    assert admin.get("/api/releases/100101").json()["friends"] == []
    assert admin.get("/api/friends").json() == {"you_share": False, "friends": []}
    admin.put("/api/sharing", json={"share_collection": True, "share_wantlist": False, "share_values": False})
    assert admin.get("/api/releases/100101").json()["friends"] == [{"name": "alex", "kind": "collection"}]
    assert admin.get("/api/releases/100201").json()["friends"] == [{"name": "alex", "kind": "want"}]
    cands = admin.get("/api/search", params={"q": "velvet static"}).json()["candidates"]
    assert next(c for c in cands if c["id"] == 100101)["friends"]
    friends = admin.get("/api/friends").json()["friends"]
    assert friends[0]["name"] == "alex" and friends[0]["collection"] == 1 and friends[0]["wantlist"] == 1
    items = admin.get(f"/api/friends/{friends[0]['id']}/items").json()["items"]
    assert items[0]["title"] == "Neon Harbour" and "value" not in items[0] and "purchase_price" not in items[0]
    # the friend turns sharing off → gone immediately
    friend.put("/api/sharing", json={"share_collection": False, "share_wantlist": False, "share_values": False})
    assert admin.get("/api/releases/100101").json()["friends"] == []
    assert admin.get(f"/api/friends/{friends[0]['id']}/items").status_code == 404


def test_values_need_separate_opt_in(admin):
    friend = make_friend(admin)
    add(friend, 100101, media_grade="VG+")
    friend.get("/api/releases/100101/price")
    friend.put("/api/sharing", json={"share_collection": True, "share_wantlist": False, "share_values": True})
    admin.put("/api/sharing", json={"share_collection": True, "share_wantlist": False, "share_values": False})
    fid = admin.get("/api/friends").json()["friends"][0]["id"]
    assert admin.get(f"/api/friends/{fid}/items").json()["items"][0]["value"] == 180.0


def test_api_answers_are_not_cached_but_covers_are(admin):
    assert admin.get("/api/me").headers["cache-control"] == "no-store"
    assert "immutable" in admin.get("/api/thumbs/100101").headers["cache-control"]


def test_opening_an_imported_record_fetches_full_details(admin):
    admin.post("/api/discogs/import", json={})
    wait_import(admin)
    r = admin.get("/api/releases/100302").json()
    assert r["country"] == "Germany" and r["matrix"] and not r.get("partial")
