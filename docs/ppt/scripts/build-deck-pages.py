"""Author SVG pages 08-21 of the Phase-0 group-meeting deck.

The deck's content authority is docs/ppt/2026-10-14-group-meeting/group-meeting-ppt-prompt.md;
this script renders that roster at the A-scale type floor (nothing below 19 px = 14.25 pt)
using the same width estimator as the ppt-master checker, so the geometric audit agrees
with the authoring arithmetic.

Layouts
  problem pages (08-13): full-width mechanism hero card, Problem band, full-width Methods
      list, then the design footnote and the `-> evidence` cross-reference;
  verification pages (14-21): full-width verdict hero card, then a left column with
      How we measured / Results (+ caveat) and a right column with the Formulas cells,
      closing on a single-line Impact strip.

Run:  python scripts/build-deck-pages.py [--check]
"""
from __future__ import annotations

import sys
from pathlib import Path

SKILL_SCRIPTS = Path(r"E:\大学\NUS\EE5003\agent\.agents\skills\ppt-master\scripts")
sys.path.insert(0, str(SKILL_SCRIPTS))
from text_measure import measure_text, wrap_text  # noqa: E402

PROJECT = Path(r"E:\大学\NUS\EE5003\agent\.agents\projects\gm1013v4_20261013")
OUT = PROJECT / "svg_output"

L, R = 64.0, 1216.0
W = R - L
LIMIT_BOTTOM = 636.0

INK = "#0F172A"
MUTED = "#64748B"
FAINT = "#94A3B8"
ACCENT = "#2563EB"
ACCENT_SOFT = "#DBEAFE"
HAIRLINE = "#E2E8F0"
SURFACE = "#F8FAFC"
STRIP = "#F1F5F9"
YH = "Microsoft YaHei"
MONO = "Consolas"

issues: list[str] = []


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def width(text: str, size: float, family: str = "Arial", weight: str = "normal") -> float:
    return measure_text(text, size=size, family=family, weight=weight)


def wrap(text: str, size: float, max_w: float, family: str = "Arial", weight: str = "normal") -> list[str]:
    lines, _widths, oversized = wrap_text(
        text, size=size, max_width=max_w, family=family, weight=weight
    )
    for unit, unit_width in oversized:
        issues.append(f"oversized unit {unit!r} ({unit_width:.0f} px > {max_w:.0f}): {text[:50]}")
    return [ln.strip() for ln in lines if ln.strip()]


def t(id_: str, x: float, y: float, size: float, fill: str, content: str,
      weight: str | None = None, family: str | None = None, anchor: str | None = None) -> str:
    attrs = f'id="{id_}" x="{x:g}" y="{y:g}" font-size="{size:g}"'
    if weight:
        attrs += f' font-weight="{weight}"'
    if family:
        attrs += f' font-family="{family}"'
    if anchor:
        attrs += f' text-anchor="{anchor}"'
    return f'  <text {attrs} fill="{fill}">{content}</text>'


def two_tone(id_: str, x: float, y: float, size: float, head: str, tail: str,
             head_fill: str = INK, tail_fill: str = MUTED) -> str:
    return (
        f'  <text id="{id_}" x="{x:g}" y="{y:g}" font-size="{size:g}">'
        f'<tspan font-weight="700" fill="{head_fill}">{esc(head)}</tspan>'
        f'<tspan fill="{tail_fill}">{esc(tail)}</tspan></text>'
    )


# ---------------------------------------------------------------- chrome


def chrome(page: int, kicker: str, title: str, gloss: str, takeaway: str) -> list[str]:
    return [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" font-family="Arial" data-pptx-page-role="content">',
        '  <rect id="bg" data-pptx-role="background" x="0" y="0" width="1280" height="720" fill="#FFFFFF"/>',
        '  <rect id="title-tick" x="64" y="44" width="8" height="30" rx="3" fill="#2563EB"/>',
        t("kicker", 86, 66, 19, MUTED, esc(kicker)),
        t("page-title", 64, 110, 40, INK, esc(title), weight=700),
        t("gloss", 64, 140, 19, MUTED, esc(gloss), family=YH),
        f'  <line id="title-rule" x1="64" y1="158" x2="1216" y2="158" stroke="{HAIRLINE}" stroke-width="1"/>',
    ]


def chrome_tail(page: int, takeaway: str) -> list[str]:
    return [
        f'  <rect id="take-bar" x="64" y="640" width="1152" height="48" fill="{STRIP}"/>',
        f'  <rect id="take-tick" x="64" y="640" width="6" height="48" fill="{ACCENT}"/>',
        t("take", 90, 671, 19, INK, esc(takeaway), weight=700),
        t("footer", 64, 712, 19, FAINT, "Phase 0 Progress Report · EE5003 · NUS"),
        t("page-num", 1216, 712, 19, FAINT, f"{page:02d} / 21", anchor="end"),
    ]


# ---------------------------------------------------------------- hero card


def hero_card(claim: str, support: str, support_fill: str = MUTED) -> tuple[list[str], float]:
    """Full-width accent-soft hero card; returns (elements, card_bottom)."""
    y = 172.0
    inner = 1040.0
    claim_lines = wrap(claim, 26, inner, weight="bold")
    support_lines = wrap(support, 19, inner)
    if len(claim_lines) > 1:
        issues.append(f"hero claim needs {len(claim_lines)} lines (keep one): {claim[:60]}")
    if len(support_lines) > 1:
        issues.append(f"hero support needs {len(support_lines)} lines: {support[:60]}")
    h = 20 + 32 * len(claim_lines) + 24 * len(support_lines)
    els = [f'  <rect id="hero" x="64" y="{y:g}" width="1152" height="{h:g}" rx="8" fill="{ACCENT_SOFT}" stroke="{ACCENT}" stroke-width="1"/>']
    cy = y + 32
    for i, line in enumerate(claim_lines, 1):
        els.append(t("hero-claim" if i == 1 else f"hero-claim{i}", 96, cy, 26, INK, esc(line), weight=700))
        cy += 32
    cy += 8 - 32 + 20  # gap before the support block
    for i, line in enumerate(support_lines, 1):
        els.append(t(f"hero-ev{i}", 96, cy, 19, support_fill, esc(line)))
        cy += 24
    return els, y + h


# ---------------------------------------------------------------- problem page


def problem_page(spec: dict) -> list[str]:
    page = spec["page"]
    out = chrome(page, spec["kicker"], spec["title"], spec["gloss"], spec["takeaway"])
    hero, card_bottom = hero_card(spec["claim"], spec["sub"])
    out += hero

    top = card_bottom + 18
    out.append(t("prob-h", 88, top + 20, 24, ACCENT, "Problem", weight=700))
    prob_lines = wrap(spec["problem"], 19, 900)
    if len(prob_lines) > 2:
        issues.append(f"p{page} problem needs {len(prob_lines)} lines")
    for i, line in enumerate(prob_lines, 1):
        out.append(t(f"prob-t{i}", 300, top + 14 + (i - 1) * 24, 19, INK, esc(line)))

    methods_top = top + 78
    out.append(t("m-h", 88, methods_top, 24, ACCENT, f"Methods — {spec['methods_label']}", weight=700))
    entries_start = methods_top + 28
    note_y, evidence_y = 580.0, 604.0
    count = len(spec["methods"])
    pitch = min(34.0, max(26.0, (note_y - 12 - entries_start) / count))
    y = entries_start
    for i, (name, tail) in enumerate(spec["methods"], 1):
        used = width(name, 19, weight="bold") + width(tail, 19)
        if used <= W:
            out.append(two_tone(f"m{i}", 64, y, 19, name, tail))
            y += pitch
        else:
            head_lines = wrap(name + tail, 19, W)
            issues.append(f"p{page} method {i} needs {len(head_lines)} lines")
            for j, line in enumerate(head_lines):
                out.append(t(f"m{i}{chr(97 + j)}", 64 if j == 0 else 88, y, 19, MUTED, esc(line)))
                y += 24
            y += 6
    y = note_y
    for i, note in enumerate(spec.get("notes", []), 1):
        note_lines = wrap(note, 19, W)
        if len(note_lines) > 1:
            issues.append(f"p{page} note {i} needs {len(note_lines)} lines")
        for j, line in enumerate(note_lines, 1):
            out.append(t(f"note{i}{j}" if j > 1 else f"note{i}", 64, y, 19, FAINT, esc(line)))
            y += 24
    ev = spec["evidence"]
    out.append(
        f'  <text id="evidence" x="64" y="{evidence_y:g}" font-size="19">'
        f'<tspan font-weight="700" fill="{ACCENT}">→ evidence: {esc(ev[0])}</tspan>'
        f'<tspan fill="{FAINT}">{esc(ev[1])}</tspan></text>'
    )
    bottom = evidence_y + 5
    if bottom > LIMIT_BOTTOM:
        issues.append(f"p{page} content bottom {bottom:.0f} > {LIMIT_BOTTOM:.0f}")
    out += chrome_tail(page, spec["takeaway"])
    out.append("</svg>")
    return out


# ---------------------------------------------------------------- verification page


def verify_page(spec: dict) -> list[str]:
    page = spec["page"]
    out = chrome(page, spec["kicker"], spec["title"], spec["gloss"], spec["takeaway"])
    hero, card_bottom = hero_card(spec["claim"], spec["evidence"])
    out += hero

    top = card_bottom + 18
    label_y = top + 20
    gloss_y = top + 42
    body_y = top + 70

    # left column: How we measured, Results (+ caveat)
    lx, lw = 64.0, 560.0
    out.append(t("how-h", lx, label_y, 24, ACCENT, "How we measured", weight=700))
    out.append(t("how-g", lx, gloss_y, 19, MUTED, "测量方法", family=YH))
    how_lines = wrap(spec["how"], 19, lw)
    if len(how_lines) > 3:
        issues.append(f"p{page} 'how we measured' needs {len(how_lines)} lines")
    y = body_y
    for i, line in enumerate(how_lines, 1):
        out.append(t(f"how-t{i}", lx, y, 19, INK, esc(line)))
        y += 24

    res_label = y + 26
    out.append(t("res-h", lx, res_label, 24, ACCENT, "Results", weight=700))
    out.append(t("res-g", lx, res_label + 22, 19, MUTED, "实测结果", family=YH))
    ry = res_label + 48
    res_lines = wrap(spec["results"], 19, lw)
    if len(res_lines) > 3:
        issues.append(f"p{page} results needs {len(res_lines)} lines")
    for i, line in enumerate(res_lines, 1):
        out.append(t(f"res-t{i}", lx, ry, 19, INK, esc(line)))
        ry += 24
    cav_lines = wrap(spec["caveat"], 19, lw)
    if len(cav_lines) > 1:
        issues.append(f"p{page} caveat needs {len(cav_lines)} lines (keep one)")
    for i, line in enumerate(cav_lines, 1):
        out.append(t(f"caveat{i}" if i > 1 else "caveat", lx, ry + 2 + (i - 1) * 24, 19, FAINT, esc(line)))
    left_bottom = ry + 2 + (len(cav_lines) - 1) * 24 + 5
    if left_bottom > LIMIT_BOTTOM:
        issues.append(f"p{page} left column bottom {left_bottom:.0f} > {LIMIT_BOTTOM:.0f}")

    # right column: Formulas
    fx, fw = 644.0, 560.0
    out.append(t("f-h", fx, label_y, 24, ACCENT, "Formulas", weight=700))
    out.append(t("f-g", fx, gloss_y, 19, MUTED, "计算公式", family=YH))
    fy = body_y
    for i, cell in enumerate(spec["formulas"], 1):
        for j, (kind, line) in enumerate(cell):
            fill = INK if kind == "f" else (MUTED if kind == "s" else FAINT)
            family = YH if kind == "g" else MONO
            xx = fx if kind != "s" else fx + 18
            out.append(t(f"f{i}{kind}", xx, fy, 19, fill, esc(line), family=family))
            fy += 21
            if width(line, 19, family=family) > fw + (18 if kind == "s" else 0):
                issues.append(f"p{page} formula {i} over column: {line[:50]}")
        fy += 10
    fy -= 10
    if fy > LIMIT_BOTTOM:
        issues.append(f"p{page} formulas bottom {fy:.0f} > {LIMIT_BOTTOM:.0f}")

    # full-width Impact strip
    out.append(t("impact-h", 64, 624, 24, ACCENT, "Impact", weight=700))
    out.append(t("impact-g", 178, 624, 19, MUTED, "结论影响", family=YH))
    imp = wrap(spec["impact"], 19, 900)
    if len(imp) > 1:
        issues.append(f"p{page} impact needs {len(imp)} lines")
    for i, line in enumerate(imp, 1):
        out.append(t(f"impact{i}", 300, 618, 19, INK, esc(line)))

    out += chrome_tail(page, spec["takeaway"])
    out.append("</svg>")
    return out


SLUGS = {
    8: "08_problem1_drift", 9: "09_problem2_loops", 10: "10_problem3_budget",
    11: "11_problem4_hallucination", 12: "12_problem5_context", 13: "13_problem6_tools",
    14: "14_verify1_sources", 15: "15_verify2_retrieval", 16: "16_verify3_storage",
    17: "17_verify4_vector", 18: "18_verify5_resume", 19: "19_verify6_loop",
    20: "20_verify7_guards", 21: "21_verify8_metrics",
}


def main() -> int:
    from deck_content import PAGES

    written = []
    for spec in PAGES:
        page = spec["page"]
        lines = (problem_page if spec["kind"] == "problem" else verify_page)(spec)
        path = OUT / f"{SLUGS[page]}.svg"
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        written.append(path.name)
    print(f"wrote {len(written)} pages: {', '.join(written)}")
    if issues:
        print("\nAUTHORING WARNINGS:")
        for item in issues:
            print(" -", item)
        return 1
    print("no width/height warnings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
