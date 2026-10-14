"""Render ppt-master SVG pages to PNG with headless Chrome for visual QA."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = Path(r"E:\大学\NUS\EE5003\agent\.chrome-profile")

HTML = """<!doctype html><meta charset="utf-8">
<style>html,body{{margin:0;padding:0;background:#fff}}svg{{display:block}}</style>
{svg}
"""


def main() -> int:
    src = Path(sys.argv[1])
    out = Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    only = sys.argv[3:] or None
    pages = sorted(p for p in src.glob("*.svg") if not only or any(o in p.name for o in only))
    tmp = out / "_html"
    tmp.mkdir(parents=True, exist_ok=True)
    for page in pages:
        svg = page.read_text(encoding="utf-8")
        svg = svg.replace('viewBox="0 0 1280 720"', 'width="1280" height="720" viewBox="0 0 1280 720"', 1)
        html = tmp / (page.stem + ".html")
        html.write_text(HTML.format(svg=svg), encoding="utf-8")
        png = out / (page.stem + ".png")
        cmd = [
            CHROME,
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--disable-extensions",
            "--force-device-scale-factor=1",
            f"--user-data-dir={PROFILE}",
            "--window-size=1320,800",
            f"--screenshot={png}",
            html.as_uri(),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        ok = png.exists() and png.stat().st_size > 2000
        print(f"{'OK ' if ok else 'FAIL'} {page.name} -> {png.name} ({png.stat().st_size if png.exists() else 0} B)")
        if not ok and res.stderr:
            print("   stderr:", res.stderr.strip()[:300])
    shutil.rmtree(tmp, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
