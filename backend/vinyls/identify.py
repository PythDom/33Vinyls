"""Identification helpers: barcode digits, OCR of photos, search queries and cover re-ranking."""
from __future__ import annotations

import io
import re
from collections import Counter
from typing import Any

from PIL import Image, ImageOps

CATNO_RE = re.compile(r"\b([A-Z]{1,6}[ -]?\d{1,3}[ .]?\d{0,5}[A-Z]?)\b")
STOPWORDS = {
    "side", "stereo", "mono", "rpm", "made", "in", "the", "and", "all", "rights", "reserved", "records",
    "record", "ltd", "inc", "of", "a", "b", "lp", "unauthorised", "unauthorized", "copying", "public",
    "performance", "broadcasting", "prohibited", "manufactured", "distributed", "by", "under", "licence",
    "license", "from", "for", "is", "on", "to", "this", "with", "produced", "www", "com",
}


def valid_ean(code: str) -> bool:
    code = re.sub(r"\D", "", code)
    if len(code) == 12:  # UPC-A → EAN-13
        code = "0" + code
    if len(code) not in (8, 13):
        return False
    digits = [int(c) for c in code]
    body, check = digits[:-1], digits[-1]
    weights = [3, 1] if len(code) == 8 else [1, 3]
    total = sum(d * weights[i % 2] for i, d in enumerate(body))
    return (10 - total % 10) % 10 == check


def load_image(data: bytes, max_side: int = 1600) -> Image.Image:
    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((max_side, max_side))
    return img


def decode_barcodes(data: bytes) -> list[str]:
    try:
        import zxingcpp
    except ImportError:  # pragma: no cover
        return []
    img = load_image(data, 2000)
    found = []
    for result in zxingcpp.read_barcodes(img):
        text = re.sub(r"\D", "", result.text or "")
        if text and text not in found:
            found.append(text)
    return found


def ocr(data: bytes, mode: str = "cover") -> str:
    """Read the text on a photo with Tesseract. Runout text is etched and often needs manual correction."""
    import pytesseract

    img = load_image(data)
    gray = ImageOps.autocontrast(img.convert("L"))
    if mode == "runout":
        gray = gray.resize((gray.width * 2, gray.height * 2))
        configs = ["--psm 6", "--psm 11"]
    else:
        configs = ["--psm 11", "--psm 3"]
    texts = []
    for config in configs:
        try:
            texts.append(pytesseract.image_to_string(gray, config=config, timeout=20))
        except Exception:
            continue
    return "\n".join(t for t in texts if t.strip())


def clean_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = re.sub(r"[^\w&'.\- ]+", " ", raw, flags=re.UNICODE)
        line = re.sub(r"\s+", " ", line).strip()
        if sum(c.isalnum() for c in line) >= 3 and line.lower() not in (l.lower() for l in lines):
            lines.append(line)
    return lines


def catalogue_numbers(text: str) -> list[str]:
    found = []
    for match in CATNO_RE.findall(text.upper()):
        candidate = match.strip(" .-")
        if any(ch.isdigit() for ch in candidate) and any(ch.isalpha() for ch in candidate) and len(candidate) >= 4:
            if candidate not in found:
                found.append(candidate)
    return found[:3]


def query_from_text(text: str, max_words: int = 6) -> str:
    words = []
    for line in clean_lines(text):
        for word in line.split():
            w = word.strip(".-'").lower()
            if len(w) >= 3 and w not in STOPWORDS and not w.isdigit() and sum(c.isalpha() for c in w) >= 3:
                words.append(word.strip(".-'"))
    counts = Counter(w.lower() for w in words)
    ordered = []
    for word in words:  # keep reading order, drop repeats
        if word.lower() not in (o.lower() for o in ordered):
            ordered.append(word)
    ordered.sort(key=lambda w: -counts[w.lower()])
    return " ".join(ordered[:max_words])


# ---------------------------------------------------------------- cover comparison

def _histogram(img: Image.Image) -> list[float]:
    small = img.convert("RGB").resize((64, 64))
    hist = [0] * 512
    for r, g, b in small.getdata():
        hist[(r >> 5) * 64 + (g >> 5) * 8 + (b >> 5)] += 1
    total = float(sum(hist))
    return [h / total for h in hist]


def _ahash(img: Image.Image) -> int:
    small = img.convert("L").resize((8, 8))
    pixels = list(small.getdata())
    avg = sum(pixels) / len(pixels)
    return sum(1 << i for i, p in enumerate(pixels) if p > avg)


def _centre_crop(img: Image.Image) -> Image.Image:
    side = min(img.size)
    left, top = (img.width - side) // 2, (img.height - side) // 2
    return img.crop((left, top, left + side, top + side))


def cover_similarity(photo: Image.Image, cover_bytes: bytes) -> float:
    """0..1 — colour histogram overlap plus a coarse layout hash. Cheap, no ML model needed."""
    cover = load_image(cover_bytes, 300)
    a, b = _centre_crop(photo), _centre_crop(cover)
    hist = sum(min(x, y) for x, y in zip(_histogram(a), _histogram(b)))
    hamming = bin(_ahash(a) ^ _ahash(b)).count("1")
    return round(0.65 * hist + 0.35 * (1 - hamming / 64), 4)


def rerank(candidates: list[dict[str, Any]], scores: dict[int, float]) -> list[dict[str, Any]]:
    for c in candidates:
        if c["id"] in scores:
            c["image_score"] = scores[c["id"]]
    return sorted(candidates, key=lambda c: -c.get("image_score", 0.0))
