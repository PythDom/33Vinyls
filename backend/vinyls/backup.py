"""Copies of the data outside the container, in the OneDrive Sync folder (same approach as Syndic).

- Live database stays in the Docker volume; consistent copies are made with SQLite's backup API.
- One direction per run: export (container → Sync folder) or restore (Sync folder → container).
- Before a restore, the current database is saved first.
- Automatic: nightly, and after a burst of changes (e.g. an import). Old snapshots are pruned.
- Files are written under a temporary name and renamed when complete (OneDrive never uploads half a file).
- Never exported: the secret key, Discogs tokens, passwords.

Command line (inside the container):
    python -m vinyls.backup export
    python -m vinyls.backup list
    python -m vinyls.backup restore /sync/restore/33vinyls-2026-11-12T0300.sqlite3
"""
from __future__ import annotations

import os
import re
import secrets
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import db, exports
from .auth import admin_user
from .config import settings

router = APIRouter(prefix="/api/admin/backups")
SNAPSHOT_RE = re.compile(r"^33vinyls-(\d{4}-\d{2}-\d{2})T(\d{4})\.sqlite3$")
KEEP_DAILY, KEEP_WEEKLY, KEEP_MONTHLY = 14, 8, 12


def available() -> tuple[bool, str]:
    d = settings.sync_dir
    if not d.exists():
        return False, f"{d} is not mounted (check the ./Sync volume in compose.yaml)."
    try:
        probe = d / ".33vinyls-write-test"
        probe.write_text("ok")
        probe.unlink()
    except OSError as exc:
        return False, f"{d} is not writable: {exc}"
    return True, ""


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=path.parent)
    with os.fdopen(fd, "wb") as f:
        f.write(data)
    os.replace(tmp, path)


def _copy_db(destination: Path) -> None:
    """Consistent copy of the live database (safe while the app is running)."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".tmp-", suffix=".sqlite3", dir=destination.parent)
    os.close(fd)
    target = sqlite3.connect(tmp)
    try:
        db.connect().backup(target)
        target.execute("DELETE FROM discogs_links")    # never export Discogs tokens
        target.execute("DELETE FROM sessions")
        target.execute("DELETE FROM oauth_pending")
        target.commit()
        target.execute("VACUUM")
    finally:
        target.close()
    os.replace(tmp, destination)


def prune(folder: Path, today: datetime | None = None) -> list[str]:
    """Keep the newest snapshot per day (14 days), per week (8 weeks) and per month (12 months)."""
    today = today or datetime.now()
    snaps = []
    for p in folder.glob("33vinyls-*.sqlite3"):
        m = SNAPSHOT_RE.match(p.name)
        if m:
            snaps.append((datetime.strptime(m.group(1) + m.group(2), "%Y-%m-%d%H%M"), p))
    snaps.sort(reverse=True)
    keep: set[Path] = set()
    days, weeks, months = set(), set(), set()
    for when, path in snaps:
        age = (today - when).days
        day, week, month = when.date(), when.isocalendar()[:2], (when.year, when.month)
        if age < KEEP_DAILY and day not in days:
            days.add(day)
            keep.add(path)
        if age < KEEP_WEEKLY * 7 and week not in weeks:
            weeks.add(week)
            keep.add(path)
        if age < KEEP_MONTHLY * 31 and month not in months:
            months.add(month)
            keep.add(path)
    removed = []
    for _, path in snaps:
        if path not in keep:
            path.unlink(missing_ok=True)
            removed.append(path.name)
    return removed


def export(reason: str = "manual") -> dict[str, Any]:
    ok, problem = available()
    if not ok:
        raise RuntimeError(problem)
    stamp = datetime.now().strftime("%Y-%m-%dT%H%M")
    snapshot = settings.sync_dir / "db" / f"33vinyls-{stamp}.sqlite3"
    _copy_db(snapshot)
    users = [dict(u) for u in db.all_("SELECT id, username FROM users")]
    for user in users:
        folder = settings.sync_dir / "export" / user["username"]
        collection = exports.user_records(user["id"], "collection")
        wantlist = exports.user_records(user["id"], "want")
        _atomic_write(folder / "collection.csv", exports.to_csv(collection).encode("utf-8"))
        _atomic_write(folder / "wantlist.csv", exports.to_csv(wantlist).encode("utf-8"))
        _atomic_write(folder / "collection.json", exports.to_json(user, collection, wantlist).encode("utf-8"))
    removed = prune(snapshot.parent)
    (settings.sync_dir / "restore").mkdir(exist_ok=True)
    db.set_state("last_export_at", db.now())
    db.set_state("last_export_file", snapshot.name)
    db.set_state("last_export_reason", reason)
    db.set_state("changes_since_export", 0)
    return {"snapshot": snapshot.name, "users": len(users), "pruned": removed}


def restore(source: Path) -> dict[str, Any]:
    """Replace the live database with a snapshot. The current database is saved first."""
    if not source.exists():
        raise FileNotFoundError(source)
    check = sqlite3.connect(f"file:{source}?mode=ro", uri=True)
    try:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("The file is damaged (integrity check failed).")
        if not check.execute("SELECT 1 FROM sqlite_master WHERE name='items'").fetchone():
            raise ValueError("This is not a 33Vinyls database.")
    finally:
        check.close()
    ok, _ = available()
    safety_dir = settings.sync_dir / "db" if ok else settings.data_dir
    safety = safety_dir / f"db-before-restore-{datetime.now().strftime('%Y-%m-%dT%H%M%S')}.sqlite3"
    # keep Discogs links and sign-ins: snapshots don't contain them; nobody should have to re-link or sign in again
    links = [dict(r) for r in db.all_("SELECT * FROM discogs_links")]
    sessions = [dict(r) for r in db.all_("SELECT * FROM sessions")]
    safety_conn = sqlite3.connect(safety)
    db.connect().backup(safety_conn)
    safety_conn.close()
    src = sqlite3.connect(source)
    try:
        src.backup(db.connect())
    finally:
        src.close()
    db.migrate()
    for link in links:
        if db.one("SELECT 1 FROM users WHERE id=?", (link["user_id"],)):
            db.run("INSERT OR REPLACE INTO discogs_links(user_id, username, method, token_enc, secret_enc, linked_at) VALUES (?,?,?,?,?,?)",
                   (link["user_id"], link["username"], link["method"], link["token_enc"], link["secret_enc"], link["linked_at"]))
    for sess in sessions:  # stay signed in on the phones
        if db.one("SELECT 1 FROM users WHERE id=?", (sess["user_id"],)):
            db.run("INSERT OR IGNORE INTO sessions(token_hash, user_id, created_at, expires_at) VALUES (?,?,?,?)",
                   (sess["token_hash"], sess["user_id"], sess["created_at"], sess["expires_at"]))
    # phones see a new generation and download everything again
    db.set_state("generation", secrets.token_hex(8))
    db.set_state("last_restore_at", db.now())
    db.set_state("last_restore_file", source.name)
    return {"restored": source.name, "saved_previous_as": str(safety)}


def restore_candidates() -> list[dict[str, Any]]:
    out = []
    for folder in ("restore", "db"):
        d = settings.sync_dir / folder
        if d.exists():
            for p in sorted(d.glob("*.sqlite3"), reverse=True):
                if not p.name.startswith(".tmp-"):
                    out.append({"file": f"{folder}/{p.name}", "size": p.stat().st_size,
                                "modified": datetime.fromtimestamp(p.stat().st_mtime).isoformat(timespec="minutes")})
    return out


def due_for_export(now: datetime) -> str | None:
    """'nightly' once a day after NIGHTLY_EXPORT, or 'changes' after a burst of edits followed by 10 quiet minutes."""
    last = db.get_state("last_export_at")
    last_dt = datetime.fromisoformat(last).astimezone() if last else None
    hh, mm = (int(x) for x in settings.nightly_export.split(":"))
    nightly = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now >= nightly and (last_dt is None or last_dt < nightly.astimezone()):
        return "nightly"
    changes = int(db.get_state("changes_since_export", "0"))
    last_change = db.get_state("last_change_at")
    if changes >= 25 and last_change:
        quiet = now.astimezone() - datetime.fromisoformat(last_change).astimezone()
        if quiet >= timedelta(minutes=10):
            return "changes"
    return None


# ---------------------------------------------------------------- admin API

class RestoreBody(BaseModel):
    file: str
    confirm: bool = False


@router.get("")
def status(user: dict = Depends(admin_user)) -> dict[str, Any]:
    ok, problem = available()
    return {
        "available": ok, "problem": problem, "folder": str(settings.sync_dir),
        "last_export_at": db.get_state("last_export_at"), "last_export_file": db.get_state("last_export_file"),
        "last_export_reason": db.get_state("last_export_reason"),
        "changes_since_export": int(db.get_state("changes_since_export", "0")),
        "nightly_at": settings.nightly_export,
        "last_restore_at": db.get_state("last_restore_at"), "last_restore_file": db.get_state("last_restore_file"),
        "files": restore_candidates() if ok else [],
    }


@router.post("/export")
def export_now(user: dict = Depends(admin_user)) -> dict[str, Any]:
    try:
        return export("manual")
    except RuntimeError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/restore")
def restore_now(body: RestoreBody, user: dict = Depends(admin_user)) -> dict[str, Any]:
    if not body.confirm:
        raise HTTPException(400, "Tick the confirmation box: this replaces all current data.")
    if not re.fullmatch(r"(restore|db)/[\w.\-]+\.sqlite3", body.file):
        raise HTTPException(400, "Unknown file.")
    try:
        return restore(settings.sync_dir / body.file)
    except (FileNotFoundError, ValueError, sqlite3.DatabaseError) as exc:
        raise HTTPException(400, f"Restore refused: {exc}") from exc


def main(argv: list[str]) -> int:
    db.migrate()
    if len(argv) >= 1 and argv[0] == "export":
        print(export("command line"))
    elif len(argv) >= 1 and argv[0] == "list":
        for f in restore_candidates():
            print(f["file"], f["modified"], f["size"])
    elif len(argv) == 2 and argv[0] == "restore":
        print(restore(Path(argv[1])))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
