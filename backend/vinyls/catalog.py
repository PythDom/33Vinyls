"""Release cache: normalised copies of Discogs releases, plus resized cover thumbnails."""
from __future__ import annotations

import io
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from PIL import Image

from . import db, discogs
from .config import settings

THUMB_SIZE = 300


def digits(text: Any) -> str:
    return re.sub(r"\D", "", str(text or ""))


def normalise_release(raw: dict[str, Any]) -> dict[str, Any]:
    """The compact shape stored on the server and on the phones (offline search/browse)."""
    artists = raw.get("artists") or []
    artist = ", ".join(re.sub(r"\s*\(\d+\)$", "", a.get("name", "")) for a in artists) or raw.get("artists_sort", "")
    identifiers = raw.get("identifiers") or []
    formats = []
    for f in raw.get("formats") or []:
        parts = [f.get("name", "")]
        if f.get("qty") and f.get("qty") not in ("1", 1):
            parts[0] = f'{f["qty"]}×{parts[0]}'
        parts += f.get("descriptions") or []
        if f.get("text"):
            parts.append(f["text"])
        formats.append(", ".join(p for p in parts if p))
    images = raw.get("images") or []
    primary = next((i for i in images if i.get("type") == "primary"), images[0] if images else None)
    return {
        "id": int(raw["id"]),
        "master_id": raw.get("master_id") or None,
        "artist": artist,
        "title": raw.get("title", ""),
        "year": int(raw["year"]) if str(raw.get("year") or "").isdigit() and int(raw["year"]) > 0 else None,
        "country": raw.get("country") or "",
        "labels": [{"name": re.sub(r"\s*\(\d+\)$", "", l.get("name", "")), "catno": l.get("catno", "")} for l in raw.get("labels") or []],
        "formats": formats,
        "barcodes": [digits(i["value"]) for i in identifiers if i.get("type") == "Barcode" and digits(i.get("value"))],
        "matrix": [i.get("value", "") for i in identifiers if i.get("type") == "Matrix / Runout"],
        "genres": raw.get("genres") or [],
        "styles": raw.get("styles") or [],
        "tracklist": [{"position": t.get("position", ""), "title": t.get("title", ""), "duration": t.get("duration", "")}
                      for t in raw.get("tracklist") or [] if t.get("type_", "track") == "track"],
        "notes": (raw.get("notes") or "")[:2000],
        "image": (primary or {}).get("uri") or raw.get("thumb") or "",
        "discogs_url": raw.get("uri") or f"https://www.discogs.com/release/{raw['id']}",
    }


def cached_release(release_id: int) -> dict[str, Any] | None:
    row = db.one("SELECT data FROM releases WHERE id=?", (release_id,))
    return json.loads(row["data"]) if row else None


async def get_release(creds: discogs.Credentials, release_id: int, refresh: bool = False) -> dict[str, Any]:
    row = db.one("SELECT data, fetched_at, complete FROM releases WHERE id=?", (release_id,))
    if row and not row["complete"]:
        refresh = True  # only the short import summary is known: get the full release
    if row and not refresh:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])
        if age < timedelta(days=settings.release_ttl_days):
            return json.loads(row["data"])
    try:
        raw = await discogs.release(creds, release_id)
    except discogs.DiscogsError:
        if row:  # keep working with the cached copy
            return json.loads(row["data"])
        raise
    release = normalise_release(raw)
    store_release(release, complete=True)
    return release


def store_release(release: dict[str, Any], complete: bool) -> None:
    """Save a normalised release; bumps its sequence number so phones pick up the change."""
    if not complete:
        existing = db.one("SELECT complete FROM releases WHERE id=?", (release["id"],))
        if existing and existing["complete"]:
            return  # never replace full data with the shorter import summary
    db.run(
        "INSERT INTO releases(id, master_id, data, fetched_at, seq, complete) VALUES (?,?,?,?,?,?) "
        "ON CONFLICT(id) DO UPDATE SET master_id=excluded.master_id, data=excluded.data, fetched_at=excluded.fetched_at, "
        "seq=excluded.seq, complete=excluded.complete",
        (release["id"], release["master_id"], db.dumps(release), db.now(), db.next_seq(), int(complete)),
    )


def release_from_basic(basic: dict[str, Any]) -> dict[str, Any]:
    """Discogs collection/wantlist entries carry a short summary (no barcodes, runouts or tracklist)."""
    raw = {
        "id": basic["id"],
        "master_id": basic.get("master_id"),
        "title": basic.get("title", ""),
        "artists": basic.get("artists") or [],
        "year": basic.get("year"),
        "labels": basic.get("labels") or [],
        "formats": basic.get("formats") or [],
        "genres": basic.get("genres") or [],
        "styles": basic.get("styles") or [],
        "images": [{"type": "primary", "uri": basic.get("cover_image") or basic.get("thumb") or ""}],
    }
    release = normalise_release(raw)
    release["partial"] = True
    return release


def summarise_search_result(r: dict[str, Any]) -> dict[str, Any]:
    title = r.get("title", "")
    artist, _, album = title.partition(" - ")
    labels = r.get("label") or []
    return {
        "id": int(r["id"]),
        "master_id": r.get("master_id") or None,
        "artist": artist if album else "",
        "title": album or title,
        "year": int(r["year"]) if str(r.get("year") or "").isdigit() else None,
        "country": r.get("country") or "",
        "label": labels[0] if labels else "",
        "catno": r.get("catno") or "",
        "format": ", ".join(r.get("format") or []),
        "barcodes": [digits(b) for b in r.get("barcode") or [] if len(digits(b)) >= 8],
        "thumb": f"/api/thumbs/{int(r['id'])}",
        "_image": r.get("cover_image") or r.get("thumb") or "",
    }


def remember_image(release_id: int, url: str) -> None:
    """Search results carry an image URL; remember it so /api/thumbs can fetch it later."""
    if not url:
        return
    if cached_release(release_id) is None:
        path = settings.thumbs_dir / f"{release_id}.src"
        settings.thumbs_dir.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.write_text(url)


def make_thumb(data: bytes) -> bytes:
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.thumbnail((THUMB_SIZE, THUMB_SIZE))
    out = io.BytesIO()
    img.save(out, "JPEG", quality=78, optimize=True)
    return out.getvalue()


async def thumb(creds: discogs.Credentials | None, release_id: int) -> bytes | None:
    settings.thumbs_dir.mkdir(parents=True, exist_ok=True)
    path = settings.thumbs_dir / f"{release_id}.jpg"
    if path.exists():
        return path.read_bytes()
    release = cached_release(release_id)
    url = release["image"] if release else ""
    src = settings.thumbs_dir / f"{release_id}.src"
    if not url and src.exists():
        url = src.read_text().strip()
    if not url and creds is not None:
        try:
            url = (await get_release(creds, release_id))["image"]
        except discogs.DiscogsError:
            url = ""
    if not url:
        return None
    try:
        data = make_thumb(await discogs.fetch_image(url))
    except Exception:
        return None
    path.write_bytes(data)
    return data
