#!/usr/bin/env python3
"""
AIgregator static site builder.

Reads markdown digests from digests/, renders them as HTML pages into docs/,
then regenerates index.html and archive.html.

Usage:
    python scripts/build.py
"""
from __future__ import annotations

import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    import markdown  # type: ignore
except ImportError:
    print("ERROR: pip install markdown", file=sys.stderr)
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
DIGESTS_DIR = ROOT / "digests"
DOCS_DIR = ROOT / "docs"
DOCS_DIGESTS = DOCS_DIR / "digests"
CSS_SRC = ROOT / "templates" / "base.css"
CSS_DST = DOCS_DIR / "assets" / "base.css"
LOGO = DOCS_DIR / "assets" / "aigregator-logo.png"

ASCII_BANNER = r"""
   _    ___  ____ ____  _____ ____    _  _____ ___  ____
  / \  |_ _|/ ___|  _ \| ____/ ___|  / \|_   _/ _ \|  _ \
 / _ \  | || |  _| |_) |  _|| |  _  / _ \ | || | | | |_) |
/ ___ \ | || |_| |  _ <| |__| |_| |/ ___ \| || |_| |  _ <
/_/   \_\___|\____|_| \_\_____\____/_/   \_\_| \___/|_| \_\
"""


def html_shell(title: str, body: str, page_class: str = "", depth: int = 0) -> str:
    """depth=0 for pages in docs/ (index, archive, about). depth=1 for docs/digests/*."""
    prefix = "../" * depth
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    digest_count = len(list(DIGESTS_DIR.glob("*.md")))
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} :: AIGREGATOR</title>
<link rel="stylesheet" href="{prefix}assets/base.css">
<link rel="icon" href="{prefix}assets/aigregator-logo.png">
</head>
<body class="{page_class}">
<div class="wrap">

<div class="banner">
  <img src="{prefix}assets/aigregator-logo.png" alt="AIgregator mascot">
  <div class="banner-text">
    <h1>AIGREGATOR</h1>
    <div class="tag">// daily AI signal, scored and cited <span class="blink"></span></div>
    <pre class="ascii">{ASCII_BANNER}</pre>
  </div>
</div>

<div class="statusbar">
  <span><b>UPLINK:</b> {now}</span>
  <span><b>PACKETS:</b> {digest_count:03d}</span>
  <span><b>STATUS:</b> <span style="color:#00ff41">ONLINE</span></span>
  <span><b>OPERATOR:</b> hermes@aigregator</span>
</div>

<nav class="menu">
  [ <a href="{prefix}index.html">LATEST</a> ]
  [ <a href="{prefix}archive.html">ARCHIVE</a> ]
  [ <a href="{prefix}about.html">ABOUT</a> ]
  [ <a href="https://github.com/brianbaldock/AIgregator">SRC</a> ]
</nav>

{body}

<footer>
  <div class="counter">VISITORS :: 0x{abs(hash(now)) % 0xFFFFFF:06X}</div>
  <p>compiled by hermes :: built {now} :: <a href="https://github.com/brianbaldock/AIgregator" style="color:var(--green-dim)">view source</a></p>
  <p>no cookies. no trackers. no LLMs were harmed in the making of this page.</p>
</footer>

</div>
</body>
</html>
"""


def render_digest_md(md_text: str) -> str:
    """Render markdown to HTML, then post-process to add score badges."""
    html = markdown.markdown(md_text, extensions=["extra", "sane_lists"])

    # Score badges: turn [N] at start of list item or paragraph into a span
    def score_repl(m: re.Match) -> str:
        n = int(m.group(1))
        cls = "score"
        if n >= 7:
            cls += " hot"
        elif n >= 5:
            cls += " fresh"
        return f'<span class="{cls}">{n:02d}</span>'

    html = re.sub(r"\[(\d+)\]", score_repl, html)
    return html


def slug_for(path: Path) -> str:
    """digests/2026-05-12.md -> 2026-05-12"""
    return path.stem


def build_digest_pages() -> list[tuple[str, str, str]]:
    """Render each markdown digest. Returns list of (slug, title, first_line)."""
    DOCS_DIGESTS.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, str, str]] = []
    for md in sorted(DIGESTS_DIR.glob("*.md"), reverse=True):
        slug = slug_for(md)
        text = md.read_text(encoding="utf-8")
        body_html = render_digest_md(text)

        # Extract first heading as title
        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else slug

        # Strip markdown formatting for preview
        first_line = re.sub(r"[#*_`\[\]()]", "", text.split("\n", 1)[0]).strip()[:120]

        page = html_shell(
            title=slug,
            body=f'<article class="digest">{body_html}</article>',
            page_class="digest-page",
            depth=1,
        )
        out = DOCS_DIGESTS / f"{slug}.html"
        out.write_text(page, encoding="utf-8")
        entries.append((slug, title, first_line))
    return entries


def build_index(entries: list[tuple[str, str, str]]) -> None:
    if not entries:
        body = """
<article class="digest">
<h2>// FEED INITIALIZING</h2>
<p>No digests yet. The first transmission drops at 0700 Pacific.</p>
<p>Stay frosty.</p>
</article>
"""
    else:
        latest_slug, latest_title, _ = entries[0]
        latest_html = (DOCS_DIGESTS / f"{latest_slug}.html").read_text(encoding="utf-8")
        # Pull just the <article> out of the latest page
        m = re.search(r'(<article class="digest">.*?</article>)', latest_html, re.DOTALL)
        body = m.group(1) if m else "<p>render error</p>"

    page = html_shell(title="latest", body=body)
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")


def build_archive(entries: list[tuple[str, str, str]]) -> None:
    rows = "\n".join(
        f'<tr><td>{slug}</td><td><a href="digests/{slug}.html">{title}</a></td></tr>'
        for slug, title, _ in entries
    )
    if not rows:
        rows = '<tr><td colspan="2"><em>// no transmissions logged yet</em></td></tr>'
    body = f"""
<article class="archive">
<h2 style="font-family:'VT323',monospace;color:var(--amber);font-size:28px;margin-top:0;">// ARCHIVE.DIR</h2>
<table>
<thead><tr><th>DATE</th><th>TRANSMISSION</th></tr></thead>
<tbody>
{rows}
</tbody>
</table>
</article>
"""
    page = html_shell(title="archive", body=body)
    (DOCS_DIR / "archive.html").write_text(page, encoding="utf-8")


def build_about() -> None:
    body = """
<article class="digest">
<h2>// ABOUT.TXT</h2>
<p><b>AIGREGATOR</b> is a daily AI news digest, scored and cited.
Generated each morning at 0700 Pacific by an autonomous Hermes agent.</p>

<h3>HOW IT WORKS</h3>
<ul>
<li>Agent scours primary lab blogs, reputable press, social signal, and arXiv every morning.</li>
<li>Each item is scored 1 through 8 based on source credibility and cross-source corroboration.</li>
<li>Higher score equals more independent reputable sources covering the same story.</li>
<li>Social-only claims (X, Reddit) are isolated to the Discourse section and never used as the sole source for a hard claim.</li>
</ul>

<h3>SCORING KEY</h3>
<ul>
<li><span class="score">01</span> to <span class="score">02</span> : social signal only</li>
<li><span class="score">03</span> : aggregator or single-source press</li>
<li><span class="score">04</span> : tier-2 outlet (Ars Technica, The Verge, Wired, named analyst)</li>
<li><span class="score fresh">05</span> : primary source (lab blog, Reuters, AP, FT)</li>
<li><span class="score fresh">06</span> : primary + one corroborating source</li>
<li><span class="score hot">07</span> to <span class="score hot">08</span> : multi-source, cross-cited story</li>
</ul>

<h3>TAGS</h3>
<ul>
<li>FIRE: cross-source story, multiple independent outlets</li>
<li>SEEDLING: open-source or non-frontier-lab item</li>
</ul>

<h3>COLOPHON</h3>
<p>Built with Python, markdown, and questionable aesthetic decisions.
Source: <a href="https://github.com/brianbaldock/AIgregator">github.com/brianbaldock/AIgregator</a></p>
</article>
"""
    page = html_shell(title="about", body=body)
    (DOCS_DIR / "about.html").write_text(page, encoding="utf-8")


def main() -> int:
    DOCS_DIR.mkdir(exist_ok=True)
    (DOCS_DIR / "assets").mkdir(exist_ok=True)
    if CSS_SRC.exists():
        shutil.copy2(CSS_SRC, CSS_DST)
    # Ensure no Jekyll
    (DOCS_DIR / ".nojekyll").touch()

    entries = build_digest_pages()
    build_index(entries)
    build_archive(entries)
    build_about()
    print(f"built {len(entries)} digest page(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
