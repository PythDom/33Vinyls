import io
import shutil

import pytest
from PIL import Image, ImageDraw, ImageFont

from vinyls import demo_data, identify, pressing


def test_valid_ean():
    assert identify.valid_ean(demo_data.ean13("505419701234"))
    assert not identify.valid_ean("5054197012340")
    assert identify.valid_ean("036000291452")  # UPC-A


def test_query_and_catno_extraction():
    text = "THE VELVET STATIC\nNeon Harbour\nSTEREO\nHL 2001\nAll rights reserved"
    assert "HL 2001" in identify.catalogue_numbers(text)
    q = identify.query_from_text(text).lower()
    assert "velvet" in q and "harbour" in q and "stereo" not in q


def test_matrix_score():
    assert pressing.matrix_score("HL-2001-A1", ["HL-2001-A1"]) == 1.0
    assert pressing.matrix_score("hl 2001 a2", ["HL-2001-A1"]) < pressing.matrix_score("hl 2001 a2", ["HL-2001-A2"])
    assert pressing.matrix_score("", ["X"]) == 0.0


def test_cover_similarity_prefers_same_cover():
    same = demo_data.cover_png(100101)
    other = demo_data.cover_png(100301)
    photo = Image.open(io.BytesIO(same)).convert("RGB").rotate(3, expand=False).resize((480, 480))
    assert identify.cover_similarity(photo, same) > identify.cover_similarity(photo, other)


def _barcode_png(code: str) -> bytes:
    import zxingcpp
    img = zxingcpp.write_barcode(zxingcpp.BarcodeFormat.EAN13, code, width=400, height=160)
    out = io.BytesIO()
    Image.fromarray(img).save(out, "PNG")
    return out.getvalue()


def test_barcode_photo_endpoint(admin):
    code = demo_data.ean13("501234567890")
    r = admin.post("/api/identify/barcode-photo", files={"photo": ("b.png", _barcode_png(code), "image/png")})
    assert r.json()["codes"] == [code]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_cover_photo_identification(admin):
    img = Image.open(io.BytesIO(demo_data.cover_png(100301))).convert("RGB")
    draw = ImageDraw.Draw(img)
    font = ImageFont.load_default(size=40)
    draw.rectangle((20, 20, 580, 90), fill=(255, 255, 255))
    draw.text((30, 30), "KESTREL UNION", fill=(0, 0, 0), font=font)
    buf = io.BytesIO()
    img.save(buf, "JPEG")
    r = admin.post("/api/identify/photo", data={"mode": "cover"}, files={"photo": ("c.jpg", buf.getvalue(), "image/jpeg")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["candidates"], body
    assert body["candidates"][0]["title"] == "Paper Satellites"
    assert body["candidates"][0]["id"] == 100301  # same cover shade wins the re-ranking


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract not installed")
def test_runout_ocr_returns_text(admin):
    img = Image.new("RGB", (700, 160), (40, 40, 40))
    ImageDraw.Draw(img).text((20, 50), "HL-2001-A2", fill=(220, 220, 220), font=ImageFont.load_default(size=56))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    r = admin.post("/api/identify/photo", data={"mode": "runout"}, files={"photo": ("r.png", buf.getvalue(), "image/png")})
    assert "2001" in r.json()["text"]
