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
    """Items changed since the cursor, plus releases and prices that are new or changed for this user's records."""
    uid = user["id"]
    rows = db.all_("SELECT * FROM items WHERE user_id=? AND seq>? ORDER BY seq LIMIT 5000", (uid, since))
    items = [_item(r) for r in rows]
    more = len(rows) == 5000
    upper = items[-1]["seq"] if more else None
    changed_ids = sorted({i["release_id"] for i in items if not i["deleted"]})
    active = "SELECT DISTINCT release_id FROM items WHERE user_id=? AND deleted=0"
    bound, bound_params = ("AND seq<=?", (upper,)) if upper is not None else ("", ())
    rel_rows = db.all_(f"SELECT data, seq FROM releases WHERE seq>? {bound} AND id IN ({active})", (since, *bound_params, uid))
    price_rows = db.all_(f"SELECT data, seq FROM prices WHERE seq>? {bound} AND release_id IN ({active})", (since, *bound_params, uid))
    releases = {json.loads(r["data"])["id"]: json.loads(r["data"]) for r in rel_rows}
    prices = {json.loads(r["data"])["release_id"]: json.loads(r["data"]) for r in price_rows}
    # records that changed (e.g. re-added) also need their release and price, whatever their age
    missing = [rid for rid in changed_ids if rid not in releases]
    for chunk in (missing[i:i + 500] for i in range(0, len(missing), 500)):
        marks = ",".join("?" * len(chunk))
        for r in db.all_(f"SELECT data FROM releases WHERE id IN ({marks})", chunk):
            d = json.loads(r["data"])
            releases[d["id"]] = d
        for r in db.all_(f"SELECT data FROM prices WHERE release_id IN ({marks})", chunk):
            d = json.loads(r["data"])
            prices.setdefault(d["release_id"], d)
    seqs = [since] + [i["seq"] for i in items] + [r["seq"] for r in rel_rows] + [r["seq"] for r in price_rows]
    cursor = upper if upper is not None else max(seqs)
    return {"cursor": cursor, "more": more, "generation": generation(), "items": items,
            "releases": list(releases.values()), "prices": list(prices.values())}


def generation() -> str:
    """Changes when the database is restored from a backup: phones then download everything again."""
    value = db.get_state("generation")
    if value is None:
        value = "g1"
        db.set_state("generation", value)
    return value


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
    if applied:
        db.set_state("changes_since_export", int(db.get_state("changes_since_export", "0")) + len(applied))
        db.set_state("last_change_at", db.now())
    return {"applied": applied, "skipped": skipped}
