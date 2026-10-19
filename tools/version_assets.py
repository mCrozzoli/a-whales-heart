"""Stamp the site's own CSS/JS references with a version before publishing.

    python3 tools/version_assets.py site <version>

GitHub Pages lets browsers cache each file for 10 minutes, so right after a
deploy a browser can pair a new index.html with an old style.css. Giving every
local reference a ?v= that changes with each deploy makes a browser fetch a
matching set:

    *.html   href="style.css"  src="darkstyle/darkstyle.js"  import("./engine.js")
    *.js     import ... from "./engine.js"

Only relative references are stamped (not https://, //, data:). The source
files stay unversioned; the publish workflow runs this on its own checkout.
Modelled on calum-organ's tools/version_assets.py.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# href="x.css" / src="dir/x.js": relative (no scheme, no leading slash), no query yet
ATTR = re.compile(r'\b(href|src)="(?![a-z]+:|/)([^"?#]+\.(?:css|js))"')
# ES module imports: from "./x.js" / import("./x.js")
IMPORT = re.compile(r'((?:\bfrom\s+|\bimport\s*\(\s*)"\.{1,2}/[^"?#]+\.js)"')


def stamp(site: Path, version: str) -> list[str]:
    if not re.fullmatch(r"[\w.-]{1,40}", version):
        raise ValueError(f"bad version {version!r}")
    changed = []
    for path in sorted(site.rglob("*")):
        if path.suffix == ".html":
            text = path.read_text(encoding="utf-8")
            new = ATTR.sub(rf'\1="\2?v={version}"', text)
            new = IMPORT.sub(rf'\1?v={version}"', new)      # inline <script type="module">

        elif path.suffix == ".js":
            text = path.read_text(encoding="utf-8")
            new = IMPORT.sub(rf'\1?v={version}"', text)
        else:
            continue
        if new != text:
            path.write_text(new, encoding="utf-8")
            changed.append(str(path.relative_to(site)))
    return changed


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    for name in stamp(Path(sys.argv[1]), sys.argv[2]):
        print("versioned", name)
