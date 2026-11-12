"""Pressing detector: rank the versions of an album and ask one question at a time."""
from __future__ import annotations

import math
import re
from difflib import SequenceMatcher
from typing import Any


def compact(text: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(text or "").upper())


def matrix_score(user_text: str, matrix_values: list[str]) -> float:
    """How well typed/OCR'd runout text matches a release's matrix entries (0..1)."""
    u = compact(user_text)
    if len(u) < 2 or not matrix_values:
        return 0.0
    best = 0.0
    for value in matrix_values:
        v = compact(value)
        if not v:
            continue
        if u == v:
            return 1.0
        ratio = SequenceMatcher(None, u, v).ratio()
        if len(u) >= 4 and (u in v or v in u):
            ratio = max(ratio, 0.85 * min(len(u), len(v)) / max(len(u), len(v)) + 0.15)
        best = max(best, ratio)
    return round(best, 3)


def version_summary(v: dict[str, Any]) -> dict[str, Any]:
    year = str(v.get("released") or "")[:4]
    return {
        "id": int(v["id"]),
        "title": v.get("title", ""),
        "format": v.get("format", ""),
        "label": re.sub(r"\s*\(\d+\)$", "", v.get("label", "") or ""),
        "catno": v.get("catno", ""),
        "country": v.get("country", "") or "",
        "year": int(year) if year.isdigit() and int(year) > 0 else None,
        "thumb": f"/api/thumbs/{int(v['id'])}",
    }


QUESTION_TEXT = {
    "country": "Which country is printed on the label or sleeve?",
    "year": "Which year is printed on the label?",
    "label": "Which record label is on the centre label?",
    "catno": "Which catalogue number is on the label or spine?",
    "format": "Which description fits the record?",
}


def score_candidates(
    versions: list[dict[str, Any]],
    details: dict[int, dict[str, Any]],
    evidence: dict[str, str],
    answers: dict[str, str],
) -> list[dict[str, Any]]:
    """versions: summaries; details: release id → normalised release (with matrix/barcodes) when fetched."""
    catno = compact(evidence.get("catno", ""))
    barcode = re.sub(r"\D", "", evidence.get("barcode", ""))
    matrix = evidence.get("matrix", "")
    ranked = []
    for v in versions:
        if any(str(v.get(attr) or "") != value for attr, value in answers.items()):
            continue
        score, reasons = 0.0, []
        if catno and compact(v["catno"]) == catno:
            score += 3
            reasons.append("catalogue number")
        d = details.get(v["id"])
        if d:
            if barcode and barcode in d.get("barcodes", []):
                score += 4
                reasons.append("barcode")
            if matrix:
                m = matrix_score(matrix, d.get("matrix", []))
                if m >= 0.6:
                    score += 5 * m
                    reasons.append(f"runout {int(m * 100)}%")
        ranked.append({**v, "score": round(score, 3), "matched": reasons})
    ranked.sort(key=lambda c: (-c["score"], c["year"] or 9999))
    return ranked


def next_question(candidates: list[dict[str, Any]], answered: set[str]) -> dict[str, Any] | None:
    """Pick the attribute that best splits the top candidates (highest entropy)."""
    if len(candidates) <= 1:
        return None
    top_score = candidates[0]["score"]
    pool = [c for c in candidates if c["score"] >= top_score - 1e-9] if top_score > 0 else candidates
    if len(pool) <= 1:
        return None
    best, best_entropy = None, 0.0
    for attr in ("country", "year", "label", "catno", "format"):
        if attr in answered:
            continue
        values = [str(c.get(attr) or "") for c in pool]
        counts = {val: values.count(val) for val in set(values) if val}
        if len(counts) < 2 or len(counts) > 10:
            continue
        n = sum(counts.values())
        entropy = -sum(k / n * math.log2(k / n) for k in counts.values())
        if entropy > best_entropy:
            best, best_entropy = (attr, counts), entropy
    if not best:
        return None
    attr, counts = best
    options = sorted(counts, key=lambda val: (-counts[val], val))
    return {"attribute": attr, "question": QUESTION_TEXT[attr], "options": options}
