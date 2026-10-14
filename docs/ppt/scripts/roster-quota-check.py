"""Quick structural QA over the Roster section of group-meeting-ppt-prompt.md.

Checks, per slide 8-21:
  - one [H]
  - [1] count 1-4, [2] <= 8 (or 5-7 methods on problem pages), [3] <= 6, [F] 1-5 on verification pages
  - problem pages (8-13): no [F], no 'How we measured', hero line contains no digit
  - verification pages (14-21): has all four block headers, no 'Why' block
Exit code 0 = all clean.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

def _repo_root() -> Path:
    """Find the repo root by walking up until the deck source is reachable.

    Location-independent on purpose: this script has already moved once
    (repo/scripts -> docs/ppt/scripts), and a hard-coded `parents[N]` breaks
    every time the folder is reorganised.
    """
    for base in [Path(__file__).resolve(), *Path(__file__).resolve().parents]:
        if (base / "docs" / "ppt").is_dir() and (base / ".agents").is_dir():
            return base
    raise SystemExit("repo root not found (expected a dir holding docs/ and .agents/)")


ROOT = _repo_root()
_MEETING_DIRS = sorted((ROOT / "docs" / "ppt").glob("*-group-meeting"))
MD = _MEETING_DIRS[-1] / "group-meeting-ppt-prompt.md" if _MEETING_DIRS else None
if MD is None or not MD.is_file():
    raise SystemExit(f"roster prompt not found under {ROOT / 'docs' / 'ppt'}")

text = MD.read_text(encoding="utf-8")
# roster section only
start = text.index("## Roster (21 slides)")
end = text.index("**Presentation logic**")
roster = text[start:end]

# split into slides: lines beginning with "N. **"
slides: dict[int, list[str]] = {}
cur: int | None = None
for line in roster.splitlines():
    m = re.match(r"^(\d{1,2})\.\s", line)
    if m:
        cur = int(m.group(1))
        slides[cur] = [line]
    elif cur is not None:
        slides[cur].append(line)

problems = []
report = []
for n in sorted(slides):
    body = "\n".join(slides[n])
    counts = {t: len(re.findall(rf"`\[{t}\]`", body)) for t in ("H", "1", "2", "3", "F")}
    report.append((n, counts))
    if n < 8 or n > 21:
        continue
    if counts["H"] != 1:
        problems.append(f"slide {n}: [H] count = {counts['H']} (expected 1)")
    if not 1 <= counts["1"] <= 4:
        problems.append(f"slide {n}: [1] count = {counts['1']} (expected 1-4)")
    if counts["2"] > 8:
        problems.append(f"slide {n}: [2] count = {counts['2']} (max 8)")
    if counts["3"] > 6:
        problems.append(f"slide {n}: [3] count = {counts['3']} (max 6)")
    if 8 <= n <= 13:  # problem page
        if counts["F"]:
            problems.append(f"slide {n}: problem page has {counts['F']} [F] line(s)")
        if "How we measured" in body or "How we verify" in body:
            problems.append(f"slide {n}: problem page carries a 'How we ...' block")
        hero = [ln for ln in slides[n] if "`[H]`" in ln]
        hero_text = " ".join(hero)
        # a diagram hero may carry design constants (e.g. the 80% / 100% budget rungs)
        if re.search(r"\d", hero_text) and "diagram" not in hero_text:
            problems.append(f"slide {n}: problem hero contains a digit: {hero_text.strip()[:90]}")
        if "→ evidence" not in body:
            problems.append(f"slide {n}: missing '→ evidence' cross-reference")
    if 14 <= n <= 21:  # verification page
        for header in ("How we measured", "Formulas", "Results", "Impact"):
            if f"`[1]` {header}" not in body:
                problems.append(f"slide {n}: missing block header '{header}'")
        if re.search(r"`\[1\]` Why\b", body):
            problems.append(f"slide {n}: verification page still has a 'Why' block")
        if not 1 <= counts["F"] <= 5:
            problems.append(f"slide {n}: [F] count = {counts['F']} (expected 1-5)")

print(f"{'slide':>5} {'[H]':>4} {'[1]':>4} {'[2]':>4} {'[3]':>4} {'[F]':>4}")
for n, c in report:
    print(f"{n:>5} {c['H']:>4} {c['1']:>4} {c['2']:>4} {c['3']:>4} {c['F']:>4}")

# type floor: no px value below 19 anywhere in the file
for m in re.finditer(r"(\d+)\s*px", text):
    if int(m.group(1)) < 19 and "1 px" not in m.group(0):
        problems.append(f"font spec below 19 px: {m.group(0)!r}")

if problems:
    print("\nISSUES:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("\nOK: roster quotas, module rules and 19 px floor all clean.")
