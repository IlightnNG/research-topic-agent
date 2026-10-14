"""Detect intra-page layout collisions in ppt-master SVG pages.

Checks, per page:
  1. text whose estimated right edge passes the content margin (x=1216);
  2. overlapping text bounding boxes (the checker only tests the root viewBox, so
     column-to-column collisions pass it silently);
  3. text crossing a tinted hero band it does not start inside.

Width estimation reuses the skill's own DrawingML estimator so the numbers match
the checker.
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

SKILL_SCRIPTS = Path(r"E:\大学\NUS\EE5003\agent\.agents\skills\ppt-master\scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))
from text_measure import measure_text  # noqa: E402

SVG_NS = "{http://www.w3.org/2000/svg}"
CONTENT_RIGHT = 1216.0
CONTENT_LEFT = 64.0
TOL = 2.0


def _tag(el: ET.Element) -> str:
    return el.tag.replace(SVG_NS, "")


def _text_content(el: ET.Element) -> str:
    parts = [el.text or ""]
    for child in el:
        if _tag(child) == "tspan":
            parts.append(child.text or "")
            parts.append(child.tail or "")
    return "".join(parts).strip()


def _width(text: str, size: float, family: str, weight: str) -> float:
    if not text:
        return 0.0
    return measure_text(text, size=size, family=family, weight=weight)


def boxes(svg: Path) -> tuple[list[dict], list[dict]]:
    root = ET.parse(svg).getroot()
    default_family = root.get("font-family", "Arial")
    texts: list[dict] = []
    rects: list[dict] = []
    for el in root.iter():
        tag = _tag(el)
        if tag == "text":
            content = _text_content(el)
            size = float(el.get("font-size", "19"))
            family = el.get("font-family", default_family)
            weight = el.get("font-weight", "normal")
            width = _width(content, size, family, weight)
            x = float(el.get("x", "0"))
            y = float(el.get("y", "0"))
            anchor = el.get("text-anchor", "start")
            if anchor == "middle":
                left = x - width / 2
            elif anchor == "end":
                left = x - width
            else:
                left = x
            texts.append(
                dict(
                    id=el.get("id", "?"),
                    text=content,
                    left=left,
                    right=left + width,
                    top=y - 0.80 * size,
                    bottom=y + 0.22 * size,
                    size=size,
                )
            )
        elif tag == "rect":
            fill = (el.get("fill") or "").upper()
            rects.append(
                dict(
                    id=el.get("id", "?"),
                    left=float(el.get("x", "0")),
                    right=float(el.get("x", "0")) + float(el.get("width", "0")),
                    top=float(el.get("y", "0")),
                    bottom=float(el.get("y", "0")) + float(el.get("height", "0")),
                    tinted=fill in {"#DBEAFE", "#EFF6FF"},
                )
            )
    return texts, rects


def overlaps(a: dict, b: dict) -> bool:
    return (
        a["left"] < b["right"] - TOL
        and b["left"] < a["right"] - TOL
        and a["top"] < b["bottom"] - TOL
        and b["top"] < a["bottom"] - TOL
    )


def audit(svg: Path) -> list[str]:
    issues: list[str] = []
    texts, rects = boxes(svg)
    for t in texts:
        if t["right"] > CONTENT_RIGHT + TOL:
            issues.append(
                f"[EDGE] {t['id']:<16} right={t['right']:.0f} (> {CONTENT_RIGHT:.0f}) :: {t['text'][:60]}"
            )
        if t["left"] < CONTENT_LEFT - TOL:
            issues.append(
                f"[EDGE] {t['id']:<16} left={t['left']:.0f} (< {CONTENT_LEFT:.0f}) :: {t['text'][:60]}"
            )
    for i, a in enumerate(texts):
        for b in texts[i + 1 :]:
            if overlaps(a, b):
                issues.append(
                    f"[TEXT] {a['id']} <-> {b['id']} "
                    f"(x {a['left']:.0f}-{a['right']:.0f} vs {b['left']:.0f}-{b['right']:.0f}, "
                    f"y {a['top']:.0f}-{a['bottom']:.0f} vs {b['top']:.0f}-{b['bottom']:.0f})"
                )
    for t in texts:
        for r in rects:
            if not r["tinted"]:
                continue
            inside = r["left"] - TOL <= t["left"] and t["right"] <= r["right"] + TOL
            if inside:
                continue
            if overlaps(t, r):
                issues.append(
                    f"[BAND] {t['id']} crosses tinted band {r['id']} "
                    f"(text x {t['left']:.0f}-{t['right']:.0f}, band {r['left']:.0f}-{r['right']:.0f})"
                )
    for t in texts:
        for r in rects:
            if r["right"] - r["left"] < 120 or r["bottom"] - r["top"] < 40:
                continue
            starts_inside = r["left"] - TOL <= t["left"] <= r["right"] - 40
            vertically_inside = r["top"] - TOL <= t["top"] and t["bottom"] <= r["bottom"] + 12
            if starts_inside and vertically_inside and t["right"] > r["right"] - 8:
                issues.append(
                    f"[CARD] {t['id']} overflows card {r['id']} by {t['right'] - r['right'] + 8:.0f}px "
                    f"(text right {t['right']:.0f} > card right {r['right']:.0f}) :: {t['text'][:50]}"
                )
    return issues


def main() -> int:
    target = Path(sys.argv[1])
    files = sorted(target.glob("*.svg"))
    total = 0
    for svg in files:
        issues = audit(svg)
        total += len(issues)
        if issues:
            print(f"\n=== {svg.name} ({len(issues)}) ===")
            for line in issues:
                print("  " + line)
    print(f"\nTOTAL ISSUES: {total} across {len(files)} pages")
    return 1 if total else 0


if __name__ == "__main__":
    raise SystemExit(main())
