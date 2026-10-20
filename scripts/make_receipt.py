"""Render a fake supermarket receipt so the receipt flow can be demonstrated offline."""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

LINES = [
    ("WHOLE MILK 1L", "1.79"),
    ("GREEK YOGURT 500G", "3.49"),
    ("FREE RANGE EGGS 12", "3.99"),
    ("CHEDDAR CHEESE BLOCK", "4.25"),
    ("SOURDOUGH LOAF", "2.15"),
    ("BANANAS 1KG", "1.10"),
    ("LIME 4 PACK", "2.00"),
    ("OLIVE OIL 500ML", "6.99"),
    ("TOMATO KETCHUP", "2.60"),
    ("BLACK PEPPER", "2.15"),
    ("COFFEE BEANS 250G", "5.50"),
]


def _font(size: int):
    for candidate in (
        "C:/Windows/Fonts/consola.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
    ):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def render(path: Path) -> Path:
    width, height = 620, 900
    image = Image.new("RGB", (width, height), (250, 248, 240))
    draw = ImageDraw.Draw(image)
    title = _font(30)
    body = _font(20)

    draw.text((width // 2, 40), "SLOW & STEADY MARKET", font=title, fill=(20, 20, 20), anchor="mm")
    draw.text((width // 2, 78), "42 Sloth Lane, Lazyburg", font=body, fill=(70, 70, 70), anchor="mm")
    draw.text((width // 2, 108), "2026-10-19  18:42", font=body, fill=(70, 70, 70), anchor="mm")
    draw.line([(40, 132), (width - 40, 132)], fill=(150, 150, 150), width=2)

    y = 160
    for name, price in LINES:
        draw.text((48, y), name, font=body, fill=(25, 25, 25))
        draw.text((width - 48, y), price, font=body, fill=(25, 25, 25), anchor="ra")
        y += 40

    draw.line([(40, y + 8), (width - 40, y + 8)], fill=(150, 150, 150), width=2)
    y += 30
    for label, value in (("SUBTOTAL", "36.11"), ("VAT", "6.05"), ("TOTAL", "42.16")):
        draw.text((48, y), label, font=body, fill=(25, 25, 25))
        draw.text((width - 48, y), value, font=body, fill=(25, 25, 25), anchor="ra")
        y += 38

    draw.text((width // 2, height - 70), "THANK YOU. GO HOME.", font=body, fill=(70, 70, 70), anchor="mm")
    draw.text((width // 2, height - 40), "CARD  ****  4242", font=body, fill=(70, 70, 70), anchor="mm")

    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, quality=95)
    return path


if __name__ == "__main__":
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("sample_photos/receipt.png")
    print(render(target))
