"""Readable exports of a user's records: CSV for Excel (EU format) and JSON."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from . import db

COLUMNS = [
    ("artist", "Artist"), ("title", "Title"), ("year", "Year"), ("country", "Country"), ("label", "Label"),
    ("catno", "Cat. no."), ("format", "Format"), ("barcode", "Barcode"), ("media_grade", "Media"),
    ("sleeve_grade", "Sleeve"), ("purchase_price", "Paid (EUR)"), ("purchase_date", "Bought on"),
    ("purchase_place", "Bought at"), ("location", "Location"), ("notes", "Notes"), ("max_price", "Max price (EUR)"),
    ("value", "Est. value (EUR)"), ("price_date", "Price date"), ("added_at", "Added"),
    ("release_id", "Discogs release"), ("discogs_url", "Discogs link"),
]


def user_records(user_id: int, kind: str) -> list[dict[str, Any]]:
    rows = db.all_(
        "SELECT i.fields, i.release_id, r.data AS release, p.data AS price FROM items i "
        "LEFT JOIN releases r ON r.id = i.release_id LEFT JOIN prices p ON p.release_id = i.release_id "
        "WHERE i.user_id=? AND i.kind=? AND i.deleted=0", (user_id, kind))
    out = []
    for row in rows:
        f = json.loads(row["fields"])
        r = json.loads(row["release"]) if row["release"] else {"id": row["release_id"]}
        p = json.loads(row["price"]) if row["price"] else {}
        grade = f.get("media_grade")
        value = (p.get("suggested") or {}).get(grade) if grade else None
        value = value or p.get("median") or p.get("lowest")
        labels = r.get("labels") or [{}]
        out.append({
            "artist": r.get("artist", ""), "title": r.get("title", ""), "year": r.get("year") or "",
            "country": r.get("country", ""), "label": labels[0].get("name", ""), "catno": labels[0].get("catno", ""),
            "format": "; ".join(r.get("formats") or []), "barcode": " ".join(r.get("barcodes") or []),
            "media_grade": grade or "", "sleeve_grade": f.get("sleeve_grade", ""),
            "purchase_price": f.get("purchase_price"), "purchase_date": f.get("purchase_date", ""),
            "purchase_place": f.get("purchase_place", ""), "location": f.get("location", ""), "notes": f.get("notes", ""),
            "max_price": f.get("max_price"), "value": value, "price_date": (p.get("fetched_at") or "")[:10],
            "added_at": (f.get("added_at") or "")[:10], "release_id": row["release_id"],
            "discogs_url": r.get("discogs_url") or f"https://www.discogs.com/release/{row['release_id']}",
        })
    out.sort(key=lambda x: (str(x["artist"]).lower(), x["year"] or 0))
    return out


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.2f}".replace(".", ",")  # decimal comma for Excel in EUR countries
    return str(value)


def to_csv(records: list[dict[str, Any]]) -> str:
    """Semicolon-separated with a BOM, so Excel (Belgian/French/German settings) opens it directly."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    writer.writerow([title for _, title in COLUMNS])
    for rec in records:
        writer.writerow([_cell(rec.get(key)) for key, _ in COLUMNS])
    return "﻿" + buf.getvalue()


def to_json(user: dict[str, Any], collection: list[dict[str, Any]], wantlist: list[dict[str, Any]]) -> str:
    return json.dumps({"user": user["username"], "exported_at": db.now(), "currency": "EUR",
                       "collection": collection, "wantlist": wantlist}, ensure_ascii=False, indent=1)
