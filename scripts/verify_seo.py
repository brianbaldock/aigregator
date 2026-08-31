#!/usr/bin/env python3
"""Verify SEO + analytics wiring in the BUILT docs/ output.

Fails closed: any missing/incorrect tag exits 1.
"""
import re
import sys
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
SITE = "https://aigregator.news"
GC = "https://aigregator.goatcounter.com/count"

# Pages built by html_shell(). BBS and scene are hand-authored standalone apps.
SHELL_PAGES = sorted(
    set(DOCS.glob("*.html")) | set(DOCS.glob("digests/*.html")) | set(DOCS.glob("weekly/*.html"))
)

failures: list[str] = []


def fail(msg: str) -> None:
    failures.append(msg)


def robots_directives(html: str, path: Path) -> list[str]:
    tags = re.findall(r'<meta\s+name="robots"\s+content="([^"]*)"', html)
    if len(tags) != 1:
        fail(f"{path}: expected exactly 1 robots meta, found {len(tags)}")
        return []
    # Token match, NOT substring: "noindex" contains "index".
    return [t.strip().split(":")[0] for t in tags[0].split(",")]


def check_page(path: Path) -> None:
    html = path.read_text(encoding="utf-8")
    rel = path.relative_to(DOCS).as_posix()

    # --- analytics ---
    if f'data-goatcounter="{GC}"' not in html:
        fail(f"{rel}: missing/incorrect data-goatcounter attribute")
    if "gc.zgo.at/count.js" not in html:
        fail(f"{rel}: missing GoatCounter script src")

    # --- indexability ---
    directives = robots_directives(html, path)
    if directives:
        if rel == "404.html":
            if "noindex" not in directives:
                fail(f"{rel}: 404 page must be noindex, got {directives}")
        elif "noindex" in directives:
            fail(f"{rel}: content page is NOINDEX ({directives})")
        elif "index" not in directives:
            fail(f"{rel}: missing 'index' directive, got {directives}")

    # --- canonical ---
    canon = re.findall(r'<link rel="canonical" href="([^"]+)"', html)
    if len(canon) != 1:
        fail(f"{rel}: expected 1 canonical, found {len(canon)}")
    elif not canon[0].startswith(SITE):
        fail(f"{rel}: canonical not absolute on {SITE}: {canon[0]}")

    # --- title / description ---
    title = re.search(r"<title>(.*?)</title>", html, re.S)
    if not title or not title.group(1).strip():
        fail(f"{rel}: empty or missing <title>")
    desc = re.search(r'<meta name="description" content="([^"]*)"', html)
    if not desc or len(desc.group(1).strip()) < 30:
        fail(f"{rel}: description missing or under 30 chars")

    # --- open graph ---
    for prop in ("og:title", "og:description", "og:url", "og:image", "og:type"):
        if f'property="{prop}"' not in html:
            fail(f"{rel}: missing {prop}")
    ogimg = re.search(r'<meta property="og:image" content="([^"]+)"', html)
    if ogimg and not ogimg.group(1).startswith("http"):
        fail(f"{rel}: og:image must be absolute, got {ogimg.group(1)}")

    # --- structured data: parse, do not just count opening tags ---
    opens = len(re.findall(r'<script type="application/ld\+json">', html))
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.S
    )
    if opens != len(blocks):
        fail(f"{rel}: {opens} ld+json tags but only {len(blocks)} parsed (malformed markup)")
    import json
    for b in blocks:
        try:
            data = json.loads(b)
        except json.JSONDecodeError as e:
            fail(f"{rel}: invalid JSON-LD: {e}")
            continue
        if "@context" not in data or "@type" not in data:
            fail(f"{rel}: JSON-LD missing @context/@type")

    if rel.startswith(("digests/", "weekly/")) and rel not in ("weekly/index.html",):
        if not blocks:
            fail(f"{rel}: article page has no JSON-LD")

    # Shell pages carry the site-level WebSite/Person graph. Without this the
    # homepage shipped ZERO structured data while the gate reported green,
    # because the JSON-LD requirement only covered article pages.
    if rel in ("index.html", "archive.html", "about.html", "weekly/index.html"):
        if not blocks:
            fail(f"{rel}: shell page has no JSON-LD (expected the WebSite graph)")
        types = set()
        for b in blocks:
            try:
                types.add(json.loads(b).get("@type"))
            except json.JSONDecodeError:
                pass
        if "WebSite" not in types:
            fail(f"{rel}: no WebSite JSON-LD block (got {sorted(t for t in types if t)})")

    # --- og:image dimension declarations must match the real asset ---
    # "existence is not correctness": a square 1.5MB logo passes a is_file()
    # check and previews cropped on every platform. Check the decoded image.
    if ogimg:
        declared = {}
        for dim in ("width", "height"):
            m = re.search(rf'<meta property="og:image:{dim}" content="(\d+)"', html)
            if not m:
                fail(f"{rel}: missing og:image:{dim}")
            else:
                declared[dim] = int(m.group(1))
        if not re.search(r'<meta property="og:image:alt" content="[^"]{10,}"', html):
            fail(f"{rel}: missing or trivial og:image:alt")

        asset = DOCS / ogimg.group(1)[len(SITE) + 1:]
        if not asset.is_file():
            fail(f"{rel}: og:image {asset.name} does not exist on disk")
        else:
            # An unavailable check is NOT a passing check.
            try:
                from PIL import Image
            except ImportError:
                fail("Pillow is required to verify og:image dimensions (pip install Pillow)")
                return
            with Image.open(asset) as im:
                real_w, real_h = im.size
            if declared.get("width") != real_w or declared.get("height") != real_h:
                fail(
                    f"{rel}: og:image declares {declared.get('width')}x{declared.get('height')} "
                    f"but {asset.name} decodes to {real_w}x{real_h}"
                )
            ratio = real_w / real_h
            if not (1.85 <= ratio <= 1.97):
                fail(
                    f"{rel}: og:image {asset.name} ratio {ratio:.2f} is outside the "
                    f"1.91:1 social-card range (will crop or letterbox)"
                )
            size = asset.stat().st_size
            if size > 300_000:
                fail(f"{rel}: og:image {asset.name} is {size:,}B, over the 300KB budget")

    # twitter:image must equal og:image -- a stale one previews the wrong art.
    twimg = re.search(r'<meta name="twitter:image" content="([^"]+)"', html)
    if ogimg and twimg and twimg.group(1) != ogimg.group(1):
        fail(f"{rel}: twitter:image does not match og:image")


def check_sitemap_and_robots() -> None:
    sm = DOCS / "sitemap.xml"
    rt = DOCS / "robots.txt"
    if not sm.exists():
        fail("sitemap.xml missing")
        return
    if not rt.exists():
        fail("robots.txt missing")
        return

    txt = rt.read_text()
    if f"Sitemap: {SITE}/sitemap.xml" not in txt:
        fail("robots.txt does not point at the sitemap")
    if re.search(r"^Disallow:\s*/\s*$", txt, re.M):
        fail("robots.txt disallows the entire site")

    locs = re.findall(r"<loc>([^<]+)</loc>", sm.read_text())
    if not locs:
        fail("sitemap.xml has no <loc> entries")
        return
    if len(locs) != len(set(locs)):
        fail("sitemap.xml contains duplicate URLs")

    # Every listed URL must exist on disk, and every built page must be listed.
    for loc in locs:
        rel = loc[len(SITE) + 1:]
        target = DOCS / (rel if rel else "index.html")
        if rel.endswith("/"):
            target = DOCS / rel / "index.html"
        if not target.exists():
            fail(f"sitemap lists nonexistent page: {loc}")

    listed = set(locs)
    for p in SHELL_PAGES:
        rel = p.relative_to(DOCS).as_posix()
        if rel == "404.html":
            if f"{SITE}/404.html" in listed:
                fail("sitemap must not list 404.html")
            continue
        url = f"{SITE}/" if rel == "index.html" else f"{SITE}/{rel}"
        if rel == "weekly/index.html":
            url = f"{SITE}/weekly/"
        if url not in listed:
            fail(f"built page not in sitemap: {rel}")


def main() -> int:
    if not SHELL_PAGES:
        print("FAIL: no pages found to check (did the build run?)")
        return 1
    for p in SHELL_PAGES:
        check_page(p)
    check_sitemap_and_robots()

    if failures:
        print(f"FAIL: {len(failures)} SEO problem(s) across {len(SHELL_PAGES)} pages")
        for f in failures[:40]:
            print(f"  - {f}")
        if len(failures) > 40:
            print(f"  ... and {len(failures) - 40} more")
        return 1
    print(f"OK: SEO + analytics verified on {len(SHELL_PAGES)} pages")
    return 0


if __name__ == "__main__":
    sys.exit(main())
