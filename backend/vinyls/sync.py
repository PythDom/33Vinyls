"""Phone ↔ server sync of the user's collection and wantlist.

The phone is offline-first: it writes locally and pushes changes; it pulls everything
changed since its last cursor (a server-wide increasing sequence number).
Conflicts: last writer wins on `updated_at`.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from . import catalog, db, discogs
from .auth import current_user

router = APIRouter(prefix="/api/sync")

ALLOWED_FIELDS = {
    "media_grade", "sleeve_grade", "purchase_price", "purchase_date", "purchase_place",
    "notes", "location", "max_price", "added_at",
}


class Op(BaseModel):
    id: str = Field(min_length=8, max_length=64)
    release_id: int
    kind: Literal["collection", "want"]
    fields: dict[str, Any] = Field(default_factory=dict)
    updated_at: str
    deleted: bool = False


class PushBody(BaseModel):
    ops: list[Op] = Field(max_length=500)


def _item(row) -> dict[str, Any]:
    return {"id": row["id"], "release_id": row["release_id"], "kind": row["kind"], "fields": json.loads(row["fields"]),
            "updated_at": row["updated_at"], "deleted": bool(row["deleted"]), "seq": row["seq"]}


@router.get("")
def pull(since: int = 0, user: dict = Depends(current_user)) -> dict[str, Any]:
    rows = db.all_("SELECT * FROM items WHERE user_id=? AND seq>? ORDER BY seq LIMIT 5000", (user["id"], since))
    items = [_item(r) for r in rows]
    release_ids = sorted({i["release_id"] for i in items if not i["deleted"]})
    releases, prices = [], []
    for chunk in (release_ids[i:i + 500] for i in range(0, len(release_ids), 500)):
        marks = ",".join("?" * len(chunk))
        releases += [json.loads(r["data"]) for r in db.all_(f"SELECT data FROM releases WHERE id IN ({marks})", chunk)]
        prices += [json.loads(r["data"]) for r in db.all_(f"SELECT data FROM prices WHERE release_id IN ({marks})", chunk)]
    cursor = items[-1]["seq"] if items else since
    more = len(rows) == 5000
    return {"cursor": cursor, "more": more, "items": items, "releases": releases, "prices": prices}


@router.post("")
async def push(body: PushBody, user: dict = Depends(current_user)) -> dict[str, Any]:
    applied, skipped = [], []
    creds = None
    for op in body.ops:
        if catalog.cached_release(op.release_id) is None and not op.deleted:
            # the phone normally only adds releases the server has already looked up
            try:
                creds = creds or discogs.get_credentials(user["id"])
                await catalog.get_release(creds, op.release_id)
            except discogs.DiscogsError as exc:
                raise HTTPException(exc.status, f"Release {op.release_id}: {exc}") from exc
        existing = db.one("SELECT user_id, updated_at FROM items WHERE id=?", (op.id,))
        if existing and existing["user_id"] != user["id"]:
            skipped.append(op.id)
            continue
        if existing and existing["updated_at"] > op.updated_at:
            skipped.append(op.id)  # server copy is newer; the phone gets it on the next pull
            continue
        fields = {k: v for k, v in op.fields.items() if k in ALLOWED_FIELDS}
        db.run(
            "INSERT INTO items(id, user_id, release_id, kind, fields, updated_at, deleted, seq) VALUES (?,?,?,?,?,?,?,?) "
            "ON CONFLICT(id) DO UPDATE SET release_id=excluded.release_id, kind=excluded.kind, fields=excluded.fields, "
            "updated_at=excluded.updated_at, deleted=excluded.deleted, seq=excluded.seq",
            (op.id, user["id"], op.release_id, op.kind, db.dumps(fields), op.updated_at, int(op.deleted), db.next_seq()),
        )
        applied.append(op.id)
    return {"applied": applied, "skipped": skipped}
