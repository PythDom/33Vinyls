import io, math, sys

from PIL import Image, ImageDraw, ImageFont
def label_png(top="KESTREL UNION", middle="NGLP 9", bottom="PAPER SATELLITES", size=900, rot=0):
    img = Image.new("RGB", (size, size), (235, 225, 200))
    d = ImageDraw.Draw(img)
    c = size / 2
    d.ellipse((20, 20, size - 20, size - 20), fill=(200, 40, 40))
    d.ellipse((c - 18, c - 18, c + 18, c + 18), fill=(20, 20, 20))
    font = ImageFont.load_default(size=size // 16)
    d.text((c, c + size * 0.13), middle, fill=(255, 255, 255), font=font, anchor="mm")
    def arc(text, radius, top_side):
        n = len(text); span = 0.11 * n
        for i, ch in enumerate(text):
            a = (-span / 2 + span * (i + 0.5) / n)
            if not top_side: a = -a
            ang = a + (0 if top_side else math.pi)
            x, y = c + radius * math.sin(ang), c - radius * math.cos(ang)
            glyph = Image.new("RGBA", (size // 10, size // 10), (0, 0, 0, 0))
            ImageDraw.Draw(glyph).text((size // 20, size // 20), ch, fill=(255, 255, 255), font=font, anchor="mm")
            deg = -math.degrees(a) if top_side else -math.degrees(a)
            glyph = glyph.rotate(deg, resample=Image.BICUBIC)
            img.paste(glyph, (int(x - size // 20), int(y - size // 20)), glyph)
    arc(top, size * 0.36, True)
    arc(bottom, size * 0.36, False)
    img = img.rotate(rot, fillcolor=(235, 225, 200))
    b = io.BytesIO(); img.save(b, "JPEG", quality=88); return b.getvalue(), img
