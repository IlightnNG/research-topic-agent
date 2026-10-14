"""Build a contact sheet from the rendered page previews (4 columns)."""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw

SRC = Path(sys.argv[1])
OUT = SRC / "_contact_sheet.png"
COLS, PAD, LABEL = 4, 12, 22

pages = sorted(p for p in SRC.glob("*.png") if not p.name.startswith("_"))
if not pages:
    raise SystemExit("no previews found")
thumbs = [Image.open(p).convert("RGB") for p in pages]
tw, th = thumbs[0].size
scale = 0.42
tw, th = int(tw * scale), int(th * scale)
rows = (len(pages) + COLS - 1) // COLS
sheet = Image.new("RGB", (COLS * tw + (COLS + 1) * PAD, rows * (th + LABEL) + (rows + 1) * PAD), "#FFFFFF")
draw = ImageDraw.Draw(sheet)
for i, (page, img) in enumerate(zip(pages, thumbs)):
    r, c = divmod(i, COLS)
    x = PAD + c * (tw + PAD)
    y = PAD + r * (th + LABEL + PAD)
    sheet.paste(img.resize((tw, th), Image.LANCZOS), (x, y))
    draw.text((x, y + th + 4), page.stem, fill="#0F172A")
sheet.save(OUT)
print(f"contact sheet: {OUT.name}  {sheet.size[0]}x{sheet.size[1]}  ({len(pages)} pages)")
