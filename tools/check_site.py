"""Check the site folder before it is published. Every gate is fatal.

    python3 tools/check_site.py site

  - clearance: no CLEARANCE-PENDING marker in any page, script or stylesheet
    (put one next to anything not yet cleared for publication: a credit,
    a licence, a sound file; remove it once cleared)
  - no symlinks: they point at files on this Mac, which GitHub doesn't have
  - no file over 95 MB (git refuses 100 MB), whole site under 1 GB (Pages limit)
  - no root-absolute links (src="/…", href="/…"): the site lives under
    /a-whales-heart/, so "/style.css" would miss it

Same gates as Dark Sonification's projects/web/deploy/publish.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

MAX_FILE, MAX_SITE = 95e6, 1e9
TEXT = {".html", ".js", ".css", ".md", ".json", ".scd"}
ROOT_ABSOLUTE = re.compile(r'\b(src|href)="/(?!/)')


def check(site: Path) -> list[str]:
    problems, total = [], 0
    for p in sorted(site.rglob("*")):
        rel = p.relative_to(site)
        if p.is_symlink():
            problems.append(f"{rel}: symlink (copy the real file in)")
            continue
        if not p.is_file():
            continue
        size = p.stat().st_size
        total += size
        if size > MAX_FILE:
            problems.append(f"{rel}: {size / 1e6:.0f} MB, git refuses files over 100 MB")
        if p.suffix in TEXT:
            text = p.read_text(encoding="utf-8", errors="ignore")
            for n, line in enumerate(text.splitlines(), 1):
                if "CLEARANCE-PENDING" in line:
                    problems.append(f"{rel}:{n}: CLEARANCE-PENDING: {line.strip()[:120]}")
            if p.suffix == ".html" and ROOT_ABSOLUTE.search(text):
                problems.append(f"{rel}: root-absolute link; use relative links")
    if total > MAX_SITE:
        problems.append(f"site is {total / 1e6:.0f} MB, over GitHub Pages' 1 GB")
    return problems


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    site = Path(sys.argv[1])
    problems = check(site)
    for msg in problems:
        print("FAIL", msg)
    if problems:
        sys.exit(f"{len(problems)} problem(s): not publishing")
    print(f"{site}: ready to publish")
