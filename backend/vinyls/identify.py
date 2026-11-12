"""Identification helpers: barcode digits, OCR of photos, search queries and cover re-ranking."""
from __future__ import annotations

import io
import math
import os
import re
import unicodedata
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any

from PIL import Image, ImageOps

# Several Tesseract passes run in parallel; one thread each avoids overloading the CPU.
os.environ.setdefault("OMP_THREAD_LIMIT", "1")

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


@dataclass
class ReadLine:
    text: str
    conf: float      # mean Tesseract confidence 0..100
    source: str      # which pass found it (straight, inverted, rot90, ring…)


@dataclass
class PhotoText:
    lines: list[ReadLine] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "\n".join(l.text for l in self.lines)

    def words(self, limit: int = 24) -> list[str]:
        """Distinct useful words, best first (shown as tappable chips on the phone)."""
        seen, out = set(), []
        for line in sorted(self.lines, key=lambda l: -l.conf):
            for word in line.text.split():
                w = word.strip(".-'&")
                key = fold(w)
                if len(key) >= 2 and key not in seen and key not in STOPWORDS and sum(c.isalpha() for c in w) >= 2:
                    seen.add(key)
                    out.append(w)
        return out[:limit]


def fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _tesseract_lines(img: Image.Image, config: str, source: str, min_conf: float = 50) -> list[ReadLine]:
    """Run Tesseract and keep only confidently read words, grouped back into lines."""
    import pytesseract

    try:
        data = pytesseract.image_to_data(img, config=config, output_type=pytesseract.Output.DICT, timeout=45)
    except Exception:
        return []
    groups: dict[tuple, list[tuple[str, float]]] = {}
    for i, word in enumerate(data["text"]):
        word = (word or "").strip()
        try:
            conf = float(data["conf"][i])
        except (TypeError, ValueError):
            conf = -1
        if not word or conf < min_conf:
            continue
        if sum(c.isalnum() for c in word) < max(1, len(word) // 2):
            continue  # mostly punctuation: noise
        key = (data["block_num"][i], data["par_num"][i], data["line_num"][i])
        groups.setdefault(key, []).append((word, conf))
    lines = []
    for words in groups.values():
        text = " ".join(w for w, _ in words)
        if sum(c.isalnum() for c in text) >= 3:
            lines.append(ReadLine(text, sum(c for _, c in words) / len(words), source))
    return lines


def _variants(img: Image.Image) -> tuple[Image.Image, Image.Image]:
    gray = ImageOps.autocontrast(img.convert("L"), cutoff=1)
    return gray, ImageOps.invert(gray)  # dark text on light, and light text on dark


def unwrap_ring(img: Image.Image, inner: float = 0.42, outer: float = 0.97, clockwise: bool = True, turns: float = 1.5) -> Image.Image:
    """Straighten the text that runs around a centre label (polar → rectangle), Pillow only.

    The photo is assumed roughly centred on the label. Unwraps 1.5 turns so words crossing
    the start angle still appear whole once. clockwise=True suits text along the top edge
    (letter tops outward); clockwise=False suits text along the bottom edge (tops inward).
    """
    side = min(img.size)
    img = img.crop(((img.width - side) // 2, (img.height - side) // 2, (img.width + side) // 2, (img.height + side) // 2))
    cx = cy = side / 2
    r_out, r_in = side / 2 * outer, side / 2 * inner
    height = int(r_out - r_in)
    width = int(2 * math.pi * (r_in + r_out) / 2 * turns)
    segments = 360
    mesh = []
    for k in range(segments):
        x0, x1 = width * k // segments, width * (k + 1) // segments
        a0 = 2 * math.pi * turns * k / segments
        a1 = 2 * math.pi * turns * (k + 1) / segments
        if not clockwise:
            a0, a1 = -a0, -a1
        top_r, bot_r = (r_out, r_in) if clockwise else (r_in, r_out)

        def pt(a: float, r: float) -> tuple[float, float]:
            # angle 0 = 12 o'clock
            return cx + r * math.sin(a), cy - r * math.cos(a)

        quad = (*pt(a0, top_r), *pt(a0, bot_r), *pt(a1, bot_r), *pt(a1, top_r))
        mesh.append(((x0, 0, x1, height), quad))
    return img.transform((width, height), Image.MESH, mesh, Image.BICUBIC)


def read_photo(data: bytes, mode: str = "cover") -> PhotoText:
    """Read the text on a cover, centre label or runout, trying several passes in parallel."""
    img = load_image(data, 1400)
    gray, inverted = _variants(img)
    jobs: list[tuple[Image.Image, str, str]] = []
    if mode == "runout":
        big = gray.resize((gray.width * 2, gray.height * 2))
        jobs = [(big, "--psm 6", "straight"), (big, "--psm 11", "sparse"), (ImageOps.invert(big), "--psm 11", "inverted")]
    else:
        jobs = [(gray, "--psm 11", "straight"), (inverted, "--psm 11", "inverted"), (gray, "--psm 3", "page")]
        if mode == "label":
            for angle in (90, 180, 270):
                jobs.append((gray.rotate(angle, expand=True), "--psm 11", f"rot{angle}"))
            for clockwise, name in ((True, "ring-top"), (False, "ring-bottom")):
                ring = ImageOps.autocontrast(unwrap_ring(img, clockwise=clockwise).convert("L"), cutoff=1)
                jobs.append((ring, "--psm 11", name))
                jobs.append((ImageOps.invert(ring), "--psm 11", name + "-inv"))
        else:
            jobs.append((gray.rotate(90, expand=True), "--psm 11", "rot90"))  # spine-style vertical text
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda j: _tesseract_lines(*j), jobs))
    merged: dict[str, ReadLine] = {}
    for line in (l for batch in results for l in batch):
        key = fold(line.text)
        if key and (key not in merged or merged[key].conf < line.conf):
            merged[key] = line
    lines = sorted(merged.values(), key=lambda l: -(l.conf * min(len(l.text), 30)))
    return PhotoText(lines[:40])


def ocr(data: bytes, mode: str = "cover") -> str:
    """Plain text read from a photo (used for runouts)."""
    return read_photo(data, mode).text


def plan_queries(read: PhotoText, max_queries: int = 6) -> list[tuple[str, str]]:
    """Several small Discogs searches instead of one big one: a single misread word
    in a big search returns nothing, because Discogs requires every word to match."""
    queries: list[tuple[str, str]] = []

    def plausible(word: str) -> bool:
        # drop OCR junk such as "SATELL\\TE?" or "GadVd": letters/digits only, not mixed-case noise
        core = word.strip(".-'&")
        if not re.fullmatch(r"[\w.'&\-]+", core, flags=re.UNICODE) or len(fold(core)) < 2:
            return False
        letters = [c for c in core if c.isalpha()]
        if len(letters) >= 4 and not (core.isupper() or core.islower() or core.istitle()):
            return False
        return True

    def add(kind: str, value: str) -> None:
        value = re.sub(r"\s+", " ", value).strip()
        if kind == "q":
            value = " ".join(w for w in value.split() if plausible(w))
        if value and (kind, value.lower()) not in {(k, v.lower()) for k, v in queries}:
            queries.append((kind, value))

    for catno in catalogue_numbers(read.text)[:2]:
        add("catno", catno)
    words = read.words()
    for line in read.lines[:6]:
        useful = [w for w in line.text.split() if fold(w) not in STOPWORDS and len(fold(w)) >= 2 and sum(c.isalpha() for c in w) >= 2]
        if useful:
            add("q", " ".join(useful[:4]))
    if len(words) >= 2:
        add("q", f"{words[0]} {words[1]}")
    if words:
        add("q", words[0])
    return queries[:max_queries]


def text_match_score(candidate: dict[str, Any], read_words: set[str]) -> float:
    """Share of the candidate's artist/title words that were read on the photo (0..1), plus catalogue number."""
    tokens = {fold(t) for t in re.split(r"[\s/,&()\-]+", f"{candidate.get('artist', '')} {candidate.get('title', '')}") if len(fold(t)) >= 2}
    tokens -= STOPWORDS
    score = len(tokens & read_words) / len(tokens) if tokens else 0.0
    catno = fold(candidate.get("catno", ""))
    if catno and len(catno) >= 4 and catno in read_words:
        score += 0.5
    return round(score, 3)


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
