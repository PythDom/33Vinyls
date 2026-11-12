"""Price card in EUR: Discogs marketplace stats + price suggestions per condition grade."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

from . import db, discogs
from .config import settings

# Goldmine grade codes used in the app → Discogs condition names
GRADES: dict[str, str] = {
    "M": "Mint (M)",
    "NM": "Near Mint (NM or M-)",
    "VG+": "Very Good Plus (VG+)",
    "VG": "Very Good (VG)",
    "G+": "Good Plus (G+)",
    "G": "Good (G)",
    "F": "Fair (F)",
    "P": "Poor (P)",
}


def _value(entry: Any) -> float | None:
    if isinstance(entry, dict) and entry.get("value") is not None:
        if entry.get("currency", settings.currency) != settings.currency:
            return None  # suggestions in another currency: the user should set EUR in Discogs seller settings
        return round(float(entry["value"]), 2)
    return None


async def price_card(creds: discogs.Credentials, release_id: int, refresh: bool = False) -> dict[str, Any]:
    row = db.one("SELECT data, fetched_at FROM prices WHERE release_id=?", (release_id,))
    if row and not refresh:
        age = datetime.now(timezone.utc) - datetime.fromisoformat(row["fetched_at"])
        if age < timedelta(hours=settings.price_ttl_hours):
            return json.loads(row["data"])
    try:
        stats = await discogs.marketplace_stats(creds, release_id)
        suggestions = await discogs.price_suggestions(creds, release_id) or {}
    except discogs.DiscogsError:
        if row:
            return {**json.loads(row["data"]), "stale": True}
        raise
    by_grade = {code: _value(suggestions.get(name)) for code, name in GRADES.items()}
    by_grade = {k: v for k, v in by_grade.items() if v is not None}
    lowest = _value((stats or {}).get("lowest_price"))
    card = {
        "release_id": release_id,
        "currency": settings.currency,
        "lowest": lowest,
        "num_for_sale": (stats or {}).get("num_for_sale"),
        "suggested": by_grade,
        "low": min(by_grade.values()) if by_grade else lowest,
        "median": by_grade.get("VG+") or by_grade.get("NM") or lowest,
        "high": max(by_grade.values()) if by_grade else None,
        "source": "Discogs marketplace" + (" + price suggestions" if by_grade else ""),
        "fetched_at": db.now(),
        "note": None if by_grade else "No per-condition suggestions: fill in your Discogs seller settings (currency EUR) to get them.",
    }
    db.run(
        "INSERT INTO prices(release_id, data, fetched_at) VALUES (?,?,?) "
        "ON CONFLICT(release_id) DO UPDATE SET data=excluded.data, fetched_at=excluded.fetched_at",
        (release_id, db.dumps(card), card["fetched_at"]),
    )
    return card


def estimate(card: dict[str, Any], media: str | None, sleeve: str | None = None) -> float | None:
    """Value for a media grade, nudged down for a worse sleeve."""
    suggested = card.get("suggested") or {}
    if media and media in suggested:
        value = suggested[media]
    else:
        value = card.get("median") or card.get("lowest")
    if value is None:
        return None
    order = list(GRADES)
    if media in order and sleeve in order:
        gap = order.index(sleeve) - order.index(media)
        if gap > 0:
            value *= max(0.6, 1 - 0.1 * gap)
    return round(value, 2)


def deal_verdict(asking: float, estimate_value: float | None) -> dict[str, Any]:
    if estimate_value is None or estimate_value <= 0:
        return {"verdict": "unknown", "ratio": None}
    ratio = asking / estimate_value
    verdict = "green" if ratio <= 0.8 else "amber" if ratio <= 1.1 else "red"
    return {"verdict": verdict, "ratio": round(ratio, 2)}
