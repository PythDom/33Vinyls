"""Import a user's Discogs collection and wantlist (runs in the background, with progress)."""
from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from . import catalog, db, discogs
from .auth import current_user
from .prices import GRADES

router = APIRouter(prefix="/api/discogs/import")

# progress per user id (in memory: an import is short-lived, and restarting simply allows a new one)
_jobs: dict[int, dict[str, Any]] = {}
_GRADE_BY_NAME = {name: code for code, name in GRADES.items()}


class ImportBody(BaseModel):
    collection: bool = True
    wantlist: bool = True


def _existing(user_id: int) -> tuple[set[str], set[tuple[int, str]]]:
    instance_ids, pairs = set(), set()
    for r in db.all_("SELECT release_id, kind, fields FROM items WHERE user_id=? AND deleted=0", (user_id,)):
        fields = json.loads(r["fields"])
        if fields.get("discogs_instance_id"):
            instance_ids.add(str(fields["discogs_instance_id"]))
        pairs.add((r["release_id"], r["kind"]))
    return instance_ids, pairs


def _add_item(user_id: int, release_id: int, kind: str, fields: dict[str, Any], updated_at: str) -> None:
    db.run(
        "INSERT INTO items(id, user_id, release_id, kind, fields, updated_at, deleted, seq) VALUES (?,?,?,?,?,?,0,?)",
        (str(uuid.uuid4()), user_id, release_id, kind, db.dumps(fields), updated_at, db.next_seq()),
    )


async def run_import(user_id: int, collection: bool, wantlist: bool) -> None:
    job = _jobs[user_id]
    try:
        creds = discogs.get_credentials(user_id)
        username = discogs.linked_username(user_id)
        instance_ids, pairs = _existing(user_id)
        if collection:
            job["step"] = "collection"
            names = {f["id"]: f["name"] for f in await discogs.collection_fields(creds, username)}
            page, pages = 1, 1
            while page <= pages:
                data = await discogs.collection_page(creds, username, page)
                pages = data.get("pagination", {}).get("pages", 1)
                job["pages"] = pages
                for entry in data.get("releases", []):
                    job["seen"] += 1
                    instance = str(entry.get("instance_id", ""))
                    rid = int(entry["id"])
                    if instance in instance_ids:
                        job["skipped"] += 1
                        continue
                    catalog.store_release(catalog.release_from_basic(entry["basic_information"]), complete=False)
                    fields: dict[str, Any] = {"discogs_instance_id": instance, "added_at": entry.get("date_added") or db.now()}
                    for note in entry.get("notes") or []:
                        name, value = names.get(note.get("field_id"), ""), (note.get("value") or "").strip()
                        if not value:
                            continue
                        if name == "Media Condition" and value in _GRADE_BY_NAME:
                            fields["media_grade"] = _GRADE_BY_NAME[value]
                        elif name == "Sleeve Condition" and value in _GRADE_BY_NAME:
                            fields["sleeve_grade"] = _GRADE_BY_NAME[value]
                        elif name == "Notes":
                            fields["notes"] = value
                    _add_item(user_id, rid, "collection", fields, db.now())
                    instance_ids.add(instance)
                    pairs.add((rid, "collection"))
                    job["added"] += 1
                page += 1
        if wantlist:
            job["step"] = "wantlist"
            page, pages = 1, 1
            while page <= pages:
                data = await discogs.wantlist_page(creds, username, page)
                pages = data.get("pagination", {}).get("pages", 1)
                for entry in data.get("wants", []):
                    job["seen"] += 1
                    rid = int(entry["id"])
                    if (rid, "want") in pairs:
                        job["skipped"] += 1
                        continue
                    catalog.store_release(catalog.release_from_basic(entry["basic_information"]), complete=False)
                    fields = {"added_at": db.now()}
                    if entry.get("notes"):
                        fields["notes"] = entry["notes"]
                    _add_item(user_id, rid, "want", fields, db.now())
                    pairs.add((rid, "want"))
                    job["added"] += 1
                page += 1
        job["state"] = "done"
        job["step"] = ""
        db.set_state("changes_since_export", int(db.get_state("changes_since_export", "0")) + job["added"])
        db.set_state("last_change_at", db.now())
    except discogs.DiscogsError as exc:
        job.update(state="error", error=str(exc))
    except Exception as exc:  # pragma: no cover - unexpected
        job.update(state="error", error=f"Import failed: {exc}")
    finally:
        job["finished_at"] = db.now()


@router.post("")
async def start(body: ImportBody, user: dict = Depends(current_user)) -> dict[str, Any]:
    try:
        discogs.get_credentials(user["id"])
        discogs.linked_username(user["id"])
    except discogs.NotLinked as exc:
        raise HTTPException(exc.status, str(exc)) from exc
    job = _jobs.get(user["id"])
    if job and job["state"] == "running":
        return job
    _jobs[user["id"]] = {"state": "running", "step": "starting", "seen": 0, "added": 0, "skipped": 0, "pages": 1,
                         "error": None, "started_at": db.now(), "finished_at": None}
    asyncio.get_running_loop().create_task(run_import(user["id"], body.collection, body.wantlist))
    return _jobs[user["id"]]


@router.get("")
def status(user: dict = Depends(current_user)) -> dict[str, Any]:
    return _jobs.get(user["id"], {"state": "idle"})
