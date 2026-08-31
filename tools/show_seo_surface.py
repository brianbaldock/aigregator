#!/usr/bin/env python3
"""Print the shipped SEO surface per page, for eyeball verification.

Read-only. Complements verify_seo.py: the gate asserts invariants, this shows
what actually landed so a human can sanity-check the values themselves.
"""

from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

PAGES = [
    "index.html",
    "archive.html",
    "about.html",
    "weekly/index.html",
    "weekly/2026-W35.html",
    "digests/2026-08-30.html",
]


def main() -> None:
    for rel in PAGES:
        p = DOCS / rel
        if not p.is_file():
            print(f"{rel}: MISSING")
            continue
        t = p.read_text(encoding="utf-8")

        og = re.search(r'<meta property="og:image" content="([^"]+)"', t)
        w = re.search(r'<meta property="og:image:width" content="(\d+)"', t)
        h = re.search(r'<meta property="og:image:height" content="(\d+)"', t)
        tw = re.search(r'<meta name="twitter:image" content="([^"]+)"', t)
        ogtype = re.search(r'<meta property="og:type" content="([^"]+)"', t)

        blocks = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', t, re.S
        )
        types = []
        for b in blocks:
            try:
                types.append(json.loads(b).get("@type"))
            except json.JSONDecodeError:
                types.append("INVALID")

        print(f"\n{rel}")
        print(f"  og:type   {ogtype.group(1) if ogtype else '-'}")
        print(f"  og:image  {og.group(1).split('/')[-1] if og else '-'} "
              f"{w.group(1) if w else '?'}x{h.group(1) if h else '?'}")
        print(f"  tw match  {bool(og and tw and og.group(1) == tw.group(1))}")
        print(f"  JSON-LD   {len(blocks)} block(s): {types}")


if __name__ == "__main__":
    main()
