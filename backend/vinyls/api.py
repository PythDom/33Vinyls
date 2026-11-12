"""Online catalogue routes: search, barcode, photo identification, releases, pressings, prices, thumbnails."""
from __future__ import annotations

import asyncio
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from . import catalog, db, discogs, identify, pressing, prices
from .auth import current_user

router = APIRouter(prefix="/api")
MAX_UPLOAD = 12 * 1024 * 1024


def _creds(user: dict) -> discogs.Credentials:
    try:
        return discogs.get_credentials(user["id"])
    except discogs.NotLinked as exc:
        raise HTTPException(exc.status, str(exc)) from exc


async def _call(coro):
    try:
        return await coro
    except discogs.DiscogsError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


def _summaries(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out, seen = [], set()
    for r in results:
        if r.get("type", "release") != "release" or int(r["id"]) in seen:
            continue
        seen.add(int(r["id"]))
        s = catalog.summarise_search_result(r)
        catalog.remember_image(s["id"], s.pop("_image"))
        out.append(s)
    return out


def _owned(user_id: int, release_ids: list[int]) -> dict[int, list[str]]:
    if not release_ids:
        return {}
    marks = ",".join("?" * len(release_ids))
    rows = db.all_(f"SELECT release_id, kind FROM items WHERE user_id=? AND deleted=0 AND release_id IN ({marks})",
                   (user_id, *release_ids))
    owned: dict[int, list[str]] = {}
    for r in rows:
        owned.setdefault(r["release_id"], []).append(r["kind"])
    return owned


def _with_owned(user: dict, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    owned = _owned(user["id"], [c["id"] for c in candidates])
    for c in candidates:
        c["owned"] = owned.get(c["id"], [])
    return candidates


@router.get("/search")
async def search(q: str = "", catno: str = "", barcode: str = "", user: dict = Depends(current_user)) -> dict[str, Any]:
    if not (q.strip() or catno.strip() or barcode.strip()):
        raise HTTPException(400, "Type something to search for.")
    results = await _call(discogs.search(_creds(user), q=q.strip(), catno=catno.strip(), barcode=barcode.strip()))
    return {"candidates": _with_owned(user, _summaries(results))}


@router.get("/identify/barcode")
async def by_barcode(code: str, user: dict = Depends(current_user)) -> dict[str, Any]:
    digits = catalog.digits(code)
    if len(digits) < 8:
        raise HTTPException(400, "That doesn't look like a barcode.")
    creds = _creds(user)
    results = await _call(discogs.search(creds, barcode=digits))
    if not results and len(digits) == 13 and digits.startswith("0"):
        results = await _call(discogs.search(creds, barcode=digits[1:]))  # EAN-13 → UPC-A
    return {"barcode": digits, "valid": identify.valid_ean(digits), "candidates": _with_owned(user, _summaries(results))}


async def _read_upload(photo: UploadFile) -> bytes:
    data = await photo.read()
    if len(data) > MAX_UPLOAD:
        raise HTTPException(413, "Photo too large (max 12 MB).")
    if not data:
        raise HTTPException(400, "Empty photo.")
    return data


@router.post("/identify/barcode-photo")
async def barcode_from_photo(photo: UploadFile = File(...), user: dict = Depends(current_user)) -> dict[str, Any]:
    data = await _read_upload(photo)
    codes = await asyncio.to_thread(identify.decode_barcodes, data)
    return {"codes": codes}


@router.post("/identify/photo")
async def by_photo(photo: UploadFile = File(...), mode: str = Form("cover"), user: dict = Depends(current_user)) -> dict[str, Any]:
    """mode: cover | label | runout. Runout returns the text only (used by the pressing picker)."""
    if mode not in {"cover", "label", "runout"}:
        raise HTTPException(400, "mode must be cover, label or runout")
    data = await _read_upload(photo)
    try:
        read = await asyncio.to_thread(identify.read_photo, data, mode)
    except Exception as exc:
        raise HTTPException(500, f"Text recognition failed: {exc}") from exc
    lines = [l.text for l in read.lines]
    words = read.words()
    if mode == "runout":
        return {"text": read.text, "lines": lines, "words": words, "candidates": []}
    creds = _creds(user)
    queries = identify.plan_queries(read)
    found: dict[int, dict[str, Any]] = {}
    hits: dict[int, int] = {}
    tried = []
    for kind, value in queries:
        params = {"catno": value} if kind == "catno" else {"q": value}
        results = await _call(discogs.search(creds, **params))
        tried.append({"kind": kind, "value": value, "results": len(results)})
        for c in _summaries(results):
            found.setdefault(c["id"], c)
            hits[c["id"]] = hits.get(c["id"], 0) + 1
        if len(found) >= 40:
            break
    read_words = {identify.fold(w) for line in lines for w in line.split()} | {identify.fold(c) for c in identify.catalogue_numbers(read.text)}
    candidates = list(found.values())
    for c in candidates:
        c["text_score"] = identify.text_match_score(c, read_words)
        c["hits"] = hits[c["id"]]
    candidates.sort(key=lambda c: (-(c["text_score"] + 0.15 * c["hits"])))
    candidates = candidates[:15]
    if mode == "cover" and candidates:
        photo_img = identify.load_image(data, 600)
        best_text = candidates[0]["text_score"]
        scores: dict[int, float] = {}
        for c in candidates[:8]:
            if c["text_score"] < best_text - 0.34:
                continue  # only compare covers among the good text matches
            thumb = await catalog.thumb(creds, c["id"])
            if thumb:
                scores[c["id"]] = identify.cover_similarity(photo_img, thumb)
        for c in candidates:
            if c["id"] in scores:
                c["image_score"] = scores[c["id"]]
        candidates.sort(key=lambda c: -(c["text_score"] + 0.15 * c["hits"] + 0.5 * c.get("image_score", 0)))
    return {"text": read.text, "lines": lines, "words": words, "tried": tried, "candidates": _with_owned(user, candidates)}


@router.get("/releases/{release_id}")
async def release(release_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    data = await _call(catalog.get_release(_creds(user), release_id))
    return {**data, "owned": _owned(user["id"], [release_id]).get(release_id, [])}


@router.get("/masters/{master_id}/versions")
async def versions(master_id: int, user: dict = Depends(current_user)) -> dict[str, Any]:
    raw = await _call(discogs.master_versions(_creds(user), master_id))
    summaries = [pressing.version_summary(v) for v in raw]
    for s, v in zip(summaries, raw):
        catalog.remember_image(s["id"], v.get("thumb", ""))
    return {"master_id": master_id, "versions": _with_owned(user, summaries)}


class PressingQuery(BaseModel):
    master_id: int
    catno: str = ""
    barcode: str = ""
    matrix: str = ""
    answers: dict[str, str] = Field(default_factory=dict)
    skip: list[str] = Field(default_factory=list)


@router.post("/pressing/match")
async def match_pressing(body: PressingQuery, user: dict = Depends(current_user)) -> dict[str, Any]:
    creds = _creds(user)
    raw = await _call(discogs.master_versions(creds, body.master_id))
    versions_ = [pressing.version_summary(v) for v in raw]
    for s, v in zip(versions_, raw):
        catalog.remember_image(s["id"], v.get("thumb", ""))
    evidence = {"catno": body.catno, "barcode": body.barcode, "matrix": body.matrix}
    details: dict[int, dict[str, Any]] = {}
    if body.matrix.strip() or body.barcode.strip():
        # matrix and barcode are only in full release data: fetch the most plausible versions (rate-limit friendly)
        prelim = pressing.score_candidates(versions_, {}, evidence, body.answers)[:15]
        for v in prelim:
            try:
                details[v["id"]] = await catalog.get_release(creds, v["id"])
            except discogs.DiscogsError:
                continue
    ranked = pressing.score_candidates(versions_, details, evidence, body.answers)
    question = pressing.next_question(ranked, set(body.answers) | set(body.skip))
    return {"candidates": _with_owned(user, ranked[:40]), "total": len(ranked), "question": question}


@router.get("/releases/{release_id}/price")
async def price(release_id: int, refresh: bool = False, user: dict = Depends(current_user)) -> dict[str, Any]:
    return await _call(prices.price_card(_creds(user), release_id, refresh=refresh))


class DealQuery(BaseModel):
    asking: float = Field(gt=0)
    media: str | None = None
    sleeve: str | None = None


@router.post("/releases/{release_id}/deal")
async def deal(release_id: int, body: DealQuery, user: dict = Depends(current_user)) -> dict[str, Any]:
    card = await _call(prices.price_card(_creds(user), release_id))
    value = prices.estimate(card, body.media, body.sleeve)
    return {"estimate": value, "currency": card["currency"], **prices.deal_verdict(body.asking, value)}


@router.get("/thumbs/{release_id}")
async def thumb(release_id: int, user: dict = Depends(current_user)) -> Response:
    creds = None
    try:
        creds = discogs.get_credentials(user["id"])
    except discogs.NotLinked:
        pass
    data = await catalog.thumb(creds, release_id)
    if data is None:
        raise HTTPException(404, "No cover available")
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=31536000, immutable"})
