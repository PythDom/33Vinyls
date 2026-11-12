"""Opt-in sharing between friends. Nothing is shared by default.

A friend's records are visible to you only if they share them AND you share something
yourself (sharing is mutual). Values and purchase prices need a separate opt-in.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from . import db, exports
from .auth import current_user

router = APIRouter(prefix="/api")


class SharingBody(BaseModel):
    share_collection: bool
    share_wantlist: bool
    share_values: bool


def settings_for(user_id: int) -> dict[str, bool]:
    row = db.one("SELECT share_collection, share_wantlist, share_values FROM users WHERE id=?", (user_id,))
    return {k: bool(row[k]) for k in ("share_collection", "share_wantlist", "share_values")} if row else {}


def viewer_shares(user_id: int) -> bool:
    s = settings_for(user_id)
    return bool(s.get("share_collection") or s.get("share_wantlist"))


@router.get("/sharing")
def get_sharing(user: dict = Depends(current_user)) -> dict[str, bool]:
    return settings_for(user["id"])


@router.put("/sharing")
def put_sharing(body: SharingBody, user: dict = Depends(current_user)) -> dict[str, bool]:
    db.run("UPDATE users SET share_collection=?, share_wantlist=?, share_values=? WHERE id=?",
           (int(body.share_collection), int(body.share_wantlist), int(body.share_values and (body.share_collection or body.share_wantlist)), user["id"]))
    return settings_for(user["id"])


def friends_with(user_id: int, release_ids: list[int]) -> dict[int, list[dict[str, str]]]:
    """For each release: which friends own or want it (only shared, mutual)."""
    if not release_ids or not viewer_shares(user_id):
        return {}
    marks = ",".join("?" * len(release_ids))
    rows = db.all_(
        f"SELECT i.release_id, i.kind, u.display_name, u.username FROM items i JOIN users u ON u.id = i.user_id "
        f"WHERE i.deleted=0 AND i.user_id<>? AND i.release_id IN ({marks}) AND "
        f"((i.kind='collection' AND u.share_collection=1) OR (i.kind='want' AND u.share_wantlist=1))",
        (user_id, *release_ids))
    out: dict[int, list[dict[str, str]]] = {}
    for r in rows:
        entry = {"name": r["display_name"] or r["username"], "kind": r["kind"]}
        if entry not in out.setdefault(r["release_id"], []):
            out[r["release_id"]].append(entry)
    return out


@router.get("/friends")
def list_friends(user: dict = Depends(current_user)) -> dict[str, Any]:
    if not viewer_shares(user["id"]):
        return {"you_share": False, "friends": []}
    rows = db.all_(
        "SELECT u.id, u.display_name, u.username, u.share_collection, u.share_wantlist, "
        "(SELECT COUNT(*) FROM items i WHERE i.user_id=u.id AND i.deleted=0 AND i.kind='collection') AS n_collection, "
        "(SELECT COUNT(*) FROM items i WHERE i.user_id=u.id AND i.deleted=0 AND i.kind='want') AS n_want "
        "FROM users u WHERE u.id<>? AND (u.share_collection=1 OR u.share_wantlist=1) ORDER BY u.display_name", (user["id"],))
    friends = [{"id": r["id"], "name": r["display_name"] or r["username"],
                "collection": r["n_collection"] if r["share_collection"] else None,
                "wantlist": r["n_want"] if r["share_wantlist"] else None} for r in rows]
    return {"you_share": True, "friends": friends}


@router.get("/friends/{friend_id}/items")
def friend_items(friend_id: int, kind: str = "collection", user: dict = Depends(current_user)) -> dict[str, Any]:
    if kind not in ("collection", "want"):
        raise HTTPException(400, "kind must be collection or want")
    friend = db.one("SELECT * FROM users WHERE id=?", (friend_id,))
    allowed = friend and viewer_shares(user["id"]) and friend_id != user["id"] and (
        friend["share_collection"] if kind == "collection" else friend["share_wantlist"])
    if not allowed:
        raise HTTPException(404, "Not shared with you.")
    records = exports.user_records(friend_id, kind)
    keep = ["artist", "title", "year", "country", "label", "catno", "format", "media_grade", "sleeve_grade", "release_id", "max_price"]
    if friend["share_values"]:
        keep += ["value"]
    mine = {r["release_id"]: r["kind"] for r in db.all_("SELECT release_id, kind FROM items WHERE user_id=? AND deleted=0", (user["id"],))}
    items = [{**{k: rec.get(k) for k in keep}, "mine": mine.get(rec["release_id"])} for rec in records]
    return {"friend": friend["display_name"] or friend["username"], "kind": kind, "items": items}


@router.get("/export/{kind}.csv")
def download_csv(kind: str, user: dict = Depends(current_user)) -> Response:
    if kind not in ("collection", "wantlist"):
        raise HTTPException(404, "Not found")
    records = exports.user_records(user["id"], "collection" if kind == "collection" else "want")
    filename = f"33vinyls-{user['username']}-{kind}-{db.now()[:10]}.csv"
    return Response(exports.to_csv(records), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def stats(user_id: int) -> dict[str, Any]:
    records = exports.user_records(user_id, "collection")
    valued = [r for r in records if r["value"]]
    paid = [r for r in records if r["purchase_price"]]
    paid_and_valued = [r for r in records if r["purchase_price"] and r["value"]]
    top = sorted(valued, key=lambda r: -r["value"])[:5]
    return {
        "records": len(records), "valued": len(valued), "total_value": round(sum(r["value"] for r in valued), 2),
        "total_paid": round(sum(r["purchase_price"] for r in paid), 2),
        "gain": round(sum(r["value"] - r["purchase_price"] for r in paid_and_valued), 2),
        "top": [{"artist": r["artist"], "title": r["title"], "value": r["value"], "release_id": r["release_id"]} for r in top],
    }


@router.get("/stats")
def get_stats(user: dict = Depends(current_user)) -> dict[str, Any]:
    return stats(user["id"])

