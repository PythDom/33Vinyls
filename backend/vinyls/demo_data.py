"""Built-in fake Discogs catalogue for demo/testing (DISCOGS_MODE=demo).

All artists, labels and records here are fictional. Responses use the same shapes
as the Discogs API so the rest of the app cannot tell the difference.
"""
from __future__ import annotations

import colorsys
import io
import re
import unicodedata
from functools import lru_cache
from typing import Any

GRADES = [
    "Mint (M)", "Near Mint (NM or M-)", "Very Good Plus (VG+)", "Very Good (VG)",
    "Good Plus (G+)", "Good (G)", "Fair (F)", "Poor (P)",
]
_GRADE_FACTOR = [1.25, 1.0, 0.75, 0.5, 0.33, 0.25, 0.15, 0.1]


def ean13(first12: str) -> str:
    digits = [int(c) for c in first12]
    total = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits))
    return first12 + str((10 - total % 10) % 10)


# master_id, artist, title, genre, style, tracks, versions
# version: id, year, country, label, catno, format descriptions, barcode12 or None, matrix list, price (NM, EUR)
_CATALOGUE: list[tuple] = [
    (9001, "The Velvet Static", "Neon Harbour", "Rock", "Psychedelic Rock",
     ["Lantern Street", "Neon Harbour", "Saltwater Radio", "Cassiopeia Drive", "Low Tide Choir", "Ferry Lights"],
     [
         (100101, 1972, "UK", "Harbourline", "HL 2001", ["LP", "Album"], None, ["HL-2001-A1", "HL-2001-B1"], 240.0),
         (100102, 1972, "UK", "Harbourline", "HL 2001", ["LP", "Album", "Repress"], None, ["HL-2001-A2", "HL-2001-B3"], 95.0),
         (100103, 1973, "Germany", "Harbourline", "6305 117", ["LP", "Album"], None, ["6305117 1Y 1", "6305117 2Y 1"], 60.0),
         (100104, 1972, "US", "Crescent Records", "CR-4410", ["LP", "Album"], None, ["CR-4410-A", "CR-4410-B"], 45.0),
         (100105, 2015, "Europe", "Harbourline", "HLLP2001", ["LP", "Album", "Reissue", "180g"], "505419701234", ["HL2001RE A", "HL2001RE B"], 24.0),
         (100106, 2022, "Europe", "Harbourline", "HLLP2001C", ["LP", "Album", "Reissue", "Limited Edition", "Orange"], "505419709876", ["HL2001RE22 A", "HL2001RE22 B"], 32.0),
     ]),
    (9002, "Marisol Okafor", "Tidal Rooms", "Jazz", "Soul-Jazz",
     ["Tidal Rooms", "Mangrove", "Seventh Floor", "Rue des Vagues", "Night Bus to Ostend"],
     [
         (100201, 1979, "France", "Disques Marée", "DM 33.112", ["LP", "Album"], None, ["DM 33112 A", "DM 33112 B"], 180.0),
         (100202, 1979, "UK", "Lowland Jazz", "LJ 504", ["LP", "Album"], None, ["LJ-504-1A", "LJ-504-1B"], 110.0),
         (100203, 1980, "Japan", "Shinkai", "SK-7731", ["LP", "Album", "Obi"], None, ["SK-7731-A", "SK-7731-B"], 150.0),
         (100204, 2019, "Europe", "Disques Marée", "DM33112RE", ["LP", "Album", "Reissue"], "376001234567", ["DM33112RE-A", "DM33112RE-B"], 28.0),
     ]),
    (9003, "Kestrel Union", "Paper Satellites", "Electronic", "Synth-pop",
     ["Paper Satellites", "Coldwave Postcard", "Motorway Sleep", "Glass Pylons", "Signal Lost"],
     [
         (100301, 1985, "UK", "Northgate", "NGLP 9", ["LP", "Album"], "501234567890", ["NGLP 9 A-1", "NGLP 9 B-1"], 38.0),
         (100302, 1985, "Germany", "Northgate", "207 114", ["LP", "Album"], "400123456789", ["207114-A", "207114-B"], 22.0),
         (100303, 2020, "UK", "Northgate", "NGLP9RE", ["LP", "Album", "Reissue", "Clear"], "501234500012", ["NGLP9RE A", "NGLP9RE B"], 27.0),
     ]),
    (9004, "Juniper Vance", "Long Way to Ardmore", "Folk, World, & Country", "Folk",
     ["Ardmore", "Blackthorn", "The Mill at Kells", "Winter Fair", "Ardmore (Reprise)"],
     [
         (100401, 1976, "Ireland", "Greenfield", "GF 1003", ["LP", "Album"], None, ["GF 1003 A1", "GF 1003 B1"], 70.0),
         (100402, 1976, "UK", "Greenfield", "GFUK 1003", ["LP", "Album"], None, ["GFUK-1003-A", "GFUK-1003-B"], 40.0),
     ]),
    (9005, "Orbital Choir", "Satellites of Love", "Electronic", "Ambient",
     ["Apogee", "Perigee", "Quiet Orbit", "Re-entry"],
     [
         (100501, 1994, "UK", "Hollow Sky", "HSKY 12", ["2×LP", "Album"], "503123450012", ["HSKY 12 A", "HSKY 12 D"], 55.0),
         (100502, 2016, "Europe", "Hollow Sky", "HSKY12RE", ["2×LP", "Album", "Reissue"], "503123459876", ["HSKY12RE-A", "HSKY12RE-D"], 30.0),
     ]),
    (9006, "Brass & Ember", "Furnace Street", "Funk / Soul", "Funk",
     ["Furnace Street", "Hot Rivets", "Coal Train Boogie", "Forge Ahead"],
     [
         (100601, 1974, "US", "Ironwood", "IW-3302", ["LP", "Album"], None, ["IW-3302-A", "IW-3302-B"], 85.0),
     ]),
    (9007, "Celeste Marlow", "Velour", "Pop", "Chanson",
     ["Velour", "Boulevard", "Minuit", "Carnet Bleu"],
     [
         (100701, 1968, "France", "Pavillon", "PAV 4021", ["LP", "Album", "Mono"], None, ["PAV 4021 A", "PAV 4021 B"], 65.0),
         (100702, 1968, "France", "Pavillon", "PAV 4021 S", ["LP", "Album", "Stereo"], None, ["PAV 4021 S A", "PAV 4021 S B"], 90.0),
     ]),
    (9008, "Dune Telegraph", "Morse Code Love", "Rock", "Post-Punk",
     ["Morse Code Love", "Static Bride", "Wireless"],
     [
         (100801, 1981, "UK", "Telegraph Wire", "WIRE 7", ["7\"", "Single", "45 RPM"], None, ["WIRE 7 A", "WIRE 7 B"], 18.0),
     ]),
]

_RELEASES: dict[int, dict[str, Any]] = {}
_MASTERS: dict[int, list[int]] = {}
_PRICE: dict[int, float] = {}


def _build() -> None:
    for master_id, artist, title, genre, style, tracks, versions in _CATALOGUE:
        _MASTERS[master_id] = []
        for rid, year, country, label, catno, descriptions, barcode12, matrix, price in versions:
            is_single = "Single" in descriptions
            fmt_name = "Vinyl"
            identifiers = []
            if barcode12:
                identifiers.append({"type": "Barcode", "value": ean13(barcode12)})
            sides = ["A", "B"] if not descriptions[0].startswith("2") else ["A", "D"]
            for side, value in zip(sides, matrix):
                identifiers.append({"type": "Matrix / Runout", "value": value, "description": f"Side {side}"})
            half = (len(tracks) + 1) // 2
            tracklist = [
                {"position": ("A" if i < half else "B") + str((i if i < half else i - half) + 1), "title": t, "duration": f"{3 + i % 4}:{(17 * (i + 1)) % 60:02d}"}
                for i, t in enumerate(tracks)
            ]
            _RELEASES[rid] = {
                "id": rid,
                "master_id": master_id,
                "title": title,
                "artists": [{"name": artist}],
                "artists_sort": artist,
                "year": year,
                "country": country,
                "labels": [{"name": label, "catno": catno}],
                "formats": [{"name": fmt_name, "qty": "2" if descriptions[0].startswith("2") else "1",
                             "descriptions": [d for d in descriptions if not d.startswith("2×")] or descriptions}],
                "identifiers": identifiers,
                "genres": [genre],
                "styles": [style],
                "tracklist": tracklist,
                "thumb": f"demo:{rid}",
                "images": [{"type": "primary", "uri": f"demo:{rid}", "uri150": f"demo:{rid}"}],
                "notes": "Demo record: fictional data for testing 33Vinyls." + (" 7-inch single." if is_single else ""),
                "released": str(year),
            }
            _MASTERS[master_id].append(rid)
            _PRICE[rid] = price


_build()


def all_release_ids() -> list[int]:
    return list(_RELEASES)


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _digits(text: str) -> str:
    return re.sub(r"\D", "", str(text))


def _format_strings(r: dict[str, Any]) -> list[str]:
    f = r["formats"][0]
    return [f["name"], *f["descriptions"]]


def _search_result(r: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": r["id"],
        "type": "release",
        "master_id": r["master_id"],
        "title": f'{r["artists"][0]["name"]} - {r["title"]}',
        "year": str(r["year"]),
        "country": r["country"],
        "label": [l["name"] for l in r["labels"]],
        "catno": r["labels"][0]["catno"],
        "format": _format_strings(r),
        "barcode": [i["value"] for i in r["identifiers"] if i["type"] == "Barcode"],
        "thumb": r["thumb"],
        "cover_image": r["thumb"],
    }


def search(q: str = "", barcode: str = "", catno: str = "", artist: str = "", release_title: str = "", type: str = "release", per_page: int = 25, **_: Any) -> list[dict[str, Any]]:
    results = []
    q_tokens = [t for t in _fold(q).split() if len(t) > 1]
    for r in _RELEASES.values():
        haystack = _fold(" ".join([r["artists"][0]["name"], r["title"], r["labels"][0]["name"], r["labels"][0]["catno"], r["country"], str(r["year"])]))
        hay_compact = haystack.replace(" ", "")
        if q_tokens:
            hits = sum(1 for t in q_tokens if t in haystack.split() or (len(t) > 3 and t in hay_compact))
            if hits < max(1, (len(q_tokens) + 1) // 2):
                continue
        if barcode and _digits(barcode) not in [_digits(i["value"]) for i in r["identifiers"] if i["type"] == "Barcode"]:
            continue
        if catno and _fold(catno).replace(" ", "") != _fold(r["labels"][0]["catno"]).replace(" ", ""):
            continue
        if artist and _fold(artist) not in _fold(r["artists"][0]["name"]):
            continue
        if release_title and _fold(release_title) not in _fold(r["title"]):
            continue
        results.append(_search_result(r))
    return results[: int(per_page)]


def release(release_id: int) -> dict[str, Any] | None:
    r = _RELEASES.get(int(release_id))
    if r is None:
        return None
    stats_ = stats(release_id)
    return {**r, "lowest_price": stats_["lowest_price"]["value"], "num_for_sale": stats_["num_for_sale"]}


def versions(master_id: int) -> list[dict[str, Any]]:
    out = []
    for rid in _MASTERS.get(int(master_id), []):
        r = _RELEASES[rid]
        out.append({
            "id": rid,
            "title": r["title"],
            "format": ", ".join(_format_strings(r)),
            "label": r["labels"][0]["name"],
            "catno": r["labels"][0]["catno"],
            "country": r["country"],
            "released": str(r["year"]),
            "major_formats": ["Vinyl"],
            "thumb": r["thumb"],
        })
    return out


def stats(release_id: int) -> dict[str, Any]:
    base = _PRICE.get(int(release_id), 20.0)
    return {
        "lowest_price": {"value": round(base * 0.55, 2), "currency": "EUR"},
        "num_for_sale": 3 + int(release_id) % 17,
        "blocked_from_sale": False,
    }


def suggestions(release_id: int) -> dict[str, Any]:
    base = _PRICE.get(int(release_id), 20.0)
    return {g: {"currency": "EUR", "value": round(base * f, 2)} for g, f in zip(GRADES, _GRADE_FACTOR)}


@lru_cache(maxsize=64)
def cover_png(release_id: int) -> bytes:
    """Simple generated cover: colour per album, slightly different shade per pressing."""
    from PIL import Image, ImageDraw, ImageFont

    r = _RELEASES.get(int(release_id))
    master = r["master_id"] if r else 0
    hue = (master * 0.137) % 1.0
    shade = 0.45 + (int(release_id) % 7) * 0.05
    rgb = tuple(int(c * 255) for c in colorsys.hsv_to_rgb(hue, 0.6, shade))
    img = Image.new("RGB", (600, 600), rgb)
    draw = ImageDraw.Draw(img)
    accent = tuple(255 - c for c in rgb)
    draw.ellipse((150, 120, 450, 420), outline=accent, width=18)
    try:
        font = ImageFont.load_default(size=44)
        small = ImageFont.load_default(size=30)
    except TypeError:  # very old Pillow
        font = small = ImageFont.load_default()
    if r:
        draw.text((40, 460), r["artists"][0]["name"].upper(), fill=(255, 255, 255), font=font)
        draw.text((40, 520), r["title"], fill=(255, 255, 255), font=small)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue()
