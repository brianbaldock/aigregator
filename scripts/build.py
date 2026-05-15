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
TEMPLATES = ROOT / "templates"
CSS_FILES = [
    (TEMPLATES / "base.css", DOCS_DIR / "assets" / "base.css"),
    (TEMPLATES / "themes.css", DOCS_DIR / "assets" / "themes.css"),
    (TEMPLATES / "terminal.css", DOCS_DIR / "assets" / "terminal.css"),
]
JS_FILES = [
    (TEMPLATES / "app.js", DOCS_DIR / "assets" / "app.js"),
]
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
<link rel="stylesheet" href="{prefix}assets/themes.css">
<link rel="stylesheet" href="{prefix}assets/terminal.css">
<link rel="icon" href="{prefix}assets/aigregator-logo.png">
<link rel="alternate" type="application/rss+xml" title="AIgregator RSS" href="{prefix}feed.xml">
<link rel="alternate" type="application/atom+xml" title="AIgregator Atom" href="{prefix}atom.xml">
</head>
<body class="{page_class}" data-theme="phosphor">
<div class="wrap">

<div class="banner">
  <img src="{prefix}assets/aigregator-logo.png" alt="AIgregator mascot">
  <div class="banner-text">
    <h1>AIGREGATOR</h1>
    <div class="tag">// daily AI signal, scored and cited <span class="blink"></span></div>
    <div class="geocities-extras"><marquee scrollamount="6" style="color:#ffff00">★ WELCOME TO AIGREGATOR ★ EST. 2026 ★ BEST VIEWED IN NETSCAPE NAVIGATOR 4 ★ SIGN MY GUESTBOOK ★ NOW WITH 90% MORE TACOS ★</marquee></div>
  </div>
</div>

<div class="statusbar">
  <span><b>UPLINK:</b> {now}</span>
  <span><b>PACKETS:</b> {digest_count:03d}</span>
  <span><b>STATUS:</b> <span style="color:#00ff41">ONLINE</span></span>
</div>

<nav class="menu">
  <a href="{prefix}index.html">LATEST</a>
  <a href="{prefix}archive.html">ARCHIVE</a>
  <a href="{prefix}about.html">ABOUT</a>
  <a href="{prefix}feed.xml">RSS</a>
  <a href="https://github.com/brianbaldock/AIgregator">SRC</a>
</nav>

{body}

<footer>
  <div class="counter">VISITORS :: 0x{abs(hash(now)) % 0xFFFFFF:06X}</div>
  <p>compiled by brian &amp; hermes :: built {now} :: <a href="https://github.com/brianbaldock/AIgregator" style="color:var(--green-dim)">view source</a></p>
  <p>no cookies. no trackers. no LLMs were harmed in the making of this page.</p>
</footer>

</div>
<script src="{prefix}assets/app.js"></script>
</body>
</html>
"""


def render_digest_md(md_text: str, slug: str = "") -> str:
    """Render markdown to HTML, then post-process to add score badges and per-story anchors."""
    # Preprocess: ensure a blank line before any list that follows a non-blank,
    # non-list line. The digest format puts "_stat line_\n- item" with no
    # gap, which sane_lists treats as paragraph continuation and collapses
    # the whole section into one <p>.
    fixed_lines: list[str] = []
    prev = ""
    for line in md_text.split("\n"):
        stripped = line.lstrip()
        is_list = stripped.startswith(("- ", "* ", "+ ")) or re.match(r"\d+\.\s", stripped)
        prev_stripped = prev.strip()
        prev_is_list = prev_stripped.startswith(("- ", "* ", "+ ")) or bool(re.match(r"\d+\.\s", prev_stripped))
        if is_list and prev_stripped and not prev_is_list:
            fixed_lines.append("")
        fixed_lines.append(line)
        prev = line
    md_text = "\n".join(fixed_lines)

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

    # Per-story permalinks: add id + copy-link anchor to <li> items in the first <ol>
    # (the TL;DR list). Pattern: <li>...<strong>Title.</strong>... -> id="story-N"
    story_counter = {"n": 0}

    def li_with_anchor(m: re.Match) -> str:
        story_counter["n"] += 1
        n = story_counter["n"]
        anchor_id = f"story-{n}"
        link_html = f' <a class="story-link" href="#{anchor_id}" title="Permalink to this story">¶</a>'
        return f'<li id="{anchor_id}">{m.group(1)}{link_html}'

    # Only process the first <ol> (TL;DR section) — find it and rewrite its <li>s
    ol_match = re.search(r"(<ol>)(.*?)(</ol>)", html, re.DOTALL)
    if ol_match:
        ol_inner = re.sub(r"<li>(.*?)(?=</li>)", li_with_anchor, ol_match.group(2), flags=re.DOTALL)
        html = html[: ol_match.start()] + ol_match.group(1) + ol_inner + ol_match.group(3) + html[ol_match.end():]

    # Add ids to h2/h3 so section deep-links work
    def heading_id(m: re.Match) -> str:
        tag, content = m.group(1), m.group(2)
        # slug from content: strip tags, lowercase, keep word chars
        plain = re.sub(r"<[^>]+>", "", content)
        plain = re.sub(r"[^\w\s-]", "", plain).strip().lower()
        hid = re.sub(r"[\s_]+", "-", plain)[:48] or f"section-{hash(content) & 0xffff:x}"
        link = f' <a class="permalink" href="#{hid}" title="Permalink">#</a>'
        return f'<{tag} id="{hid}">{content}{link}</{tag}>'

    html = re.sub(r"<(h[123])>(.*?)</\1>", heading_id, html)
    return html


def slug_for(path: Path) -> str:
    """digests/2026-05-12.md -> 2026-05-12"""
    return path.stem


def build_digest_pages() -> list[dict]:
    """Render each markdown digest. Returns list of dicts with slug/title/preview/meta."""
    DOCS_DIGESTS.mkdir(parents=True, exist_ok=True)
    entries: list[dict] = []
    total_warnings = 0
    # First pass: collect meta + clean text per digest (oldest -> newest order)
    digests_data: list[dict] = []
    for md in sorted(DIGESTS_DIR.glob("*.md")):
        slug = slug_for(md)
        text = md.read_text(encoding="utf-8")
        text, warns = strip_bare_domain_citations(text)
        if warns:
            print(f"[{slug}] cleaned {len(warns)} bare-domain citation(s):")
            for w in warns:
                print(w)
            total_warnings += len(warns)
        meta = extract_digest_meta(text)
        digests_data.append({"slug": slug, "text": text, "meta": meta, "md_path": md})

    # Second pass: render with knowledge of previous day for diff
    prev_tldr_set: set[str] = set()
    for i, d in enumerate(digests_data):
        slug, text, meta = d["slug"], d["text"], d["meta"]

        # Yesterday-diff: how many TL;DR titles carried over vs are new
        cur_titles = {t.lower()[:50] for t in meta["tldr"]}
        carryover = len(cur_titles & prev_tldr_set) if prev_tldr_set else 0
        new_count = len(cur_titles) - carryover if cur_titles else 0
        diff_html = ""
        if prev_tldr_set:
            diff_html = (
                f'<div class="diff-strip">'
                f'<span class="diff-new">↑ {new_count} new</span> · '
                f'<span class="diff-carry">↻ {carryover} carryover from yesterday</span>'
                f'</div>'
            )
        prev_tldr_set = cur_titles

        # Source diversity badge
        diversity_html = ""
        if meta["diversity_warn"]:
            top = next(iter(meta["sources"])) if meta["sources"] else "?"
            diversity_html = (
                f'<div class="diversity-badge" title="More than 40% of citations come from a single source">'
                f'⚠ THIN SIGNAL · {meta["top_source_share"]}% from {top}'
                f'</div>'
            )

        body_html = render_digest_md(text)

        # Reading time (200 wpm) + share strip
        word_count = len(re.findall(r"\b\w+\b", text))
        read_min = max(1, round(word_count / 200))
        share_url = f"{SITE_URL}/digests/{slug}.html"
        from urllib.parse import quote
        share_text = quote(f"AIgregator daily digest — {slug}")
        meta_strip = f"""<div class="meta-strip">
  <span class="meta-item">📖 {read_min} min read · {word_count:,} words · 📡 {meta['total_sources']} unique sources</span>
  <span class="meta-share">
    <span class="meta-label">SHARE:</span>
    <a href="https://twitter.com/intent/tweet?text={share_text}&amp;url={quote(share_url)}" target="_blank" rel="noopener" title="Share on X">X</a>
    <a href="https://bsky.app/intent/compose?text={share_text}%20{quote(share_url)}" target="_blank" rel="noopener" title="Share on Bluesky">BSKY</a>
    <a href="https://www.linkedin.com/sharing/share-offsite/?url={quote(share_url)}" target="_blank" rel="noopener" title="Share on LinkedIn">LI</a>
    <a href="#" class="copy-link" data-url="{share_url}" title="Copy link">COPY</a>
  </span>
</div>"""
        body_html = meta_strip + diff_html + diversity_html + body_html

        title_match = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = title_match.group(1).strip() if title_match else slug
        first_line = re.sub(r"[#*_`\[\]()]", "", text.split("\n", 1)[0]).strip()[:120]

        page = html_shell(
            title=slug,
            body=f'<article class="digest">{body_html}</article>',
            page_class="digest-page",
            depth=1,
        )
        out = DOCS_DIGESTS / f"{slug}.html"
        out.write_text(page, encoding="utf-8")
        entries.append({
            "slug": slug,
            "title": title,
            "preview": first_line,
            "meta": meta,
            "read_min": read_min,
            "word_count": word_count,
        })

    # Reverse so callers (index/archive) get newest first
    entries.reverse()
    return entries


def build_index(entries: list[dict]) -> None:
    if not entries:
        body = """
<article class="digest">
<h2>// FEED INITIALIZING</h2>
<p>No digests yet. The first transmission drops at 0700 Pacific.</p>
<p>Stay frosty.</p>
</article>
"""
    else:
        latest_slug = entries[0]["slug"]
        latest_html = (DOCS_DIGESTS / f"{latest_slug}.html").read_text(encoding="utf-8")
        m = re.search(r'(<article class="digest">.*?</article>)', latest_html, re.DOTALL)
        body = m.group(1) if m else "<p>render error</p>"

    page = html_shell(title="latest", body=body)
    (DOCS_DIR / "index.html").write_text(page, encoding="utf-8")


def build_archive(entries: list[dict]) -> None:
    # Build archive.json sidecar for client-side filtering
    import json
    archive_data = [
        {
            "slug": e["slug"],
            "title": e["title"],
            "themes": list(e["meta"]["themes"].keys()),
            "sources": list(e["meta"]["sources"].keys())[:5],
            "diversity_warn": e["meta"]["diversity_warn"],
            "read_min": e["read_min"],
        }
        for e in entries
    ]
    (DOCS_DIR / "archive.json").write_text(json.dumps(archive_data, indent=2), encoding="utf-8")

    # Collect all themes for filter chips
    from collections import Counter
    all_themes: Counter = Counter()
    for e in entries:
        for t in e["meta"]["themes"]:
            all_themes[t] += 1
    theme_chips = "".join(
        f'<button class="filter-chip" data-theme="{t}">{t} <span class="chip-count">{c}</span></button>'
        for t, c in all_themes.most_common(20)
    )

    rows_list = []
    for e in entries:
        themes_attr = ",".join(e["meta"]["themes"].keys())
        warn_html = ' <span class="diversity-tag" title="thin signal">⚠</span>' if e["meta"]["diversity_warn"] else ""
        rows_list.append(
            f'<tr data-themes="{themes_attr}" data-slug="{e["slug"]}">'
            f'<td>{e["slug"]}</td>'
            f'<td><a href="digests/{e["slug"]}.html">{e["title"]}</a>'
            f'{warn_html}'
            f' <span class="archive-meta">📖 {e["read_min"]}m · 📡 {e["meta"]["total_sources"]}</span></td>'
            f'</tr>'
        )
    rows = "\n".join(rows_list)
    if not rows:
        rows = '<tr><td colspan="2"><em>// no transmissions logged yet</em></td></tr>'
    body = f"""
<article class="archive">
<h2 style="font-family:'VT323',monospace;color:var(--amber);font-size:28px;margin-top:0;">// ARCHIVE.DIR</h2>
<div class="archive-controls">
  <input type="search" id="archive-search" placeholder="filter by keyword..." autocomplete="off">
  <div class="filter-chips">
    <button class="filter-chip filter-clear" data-theme="">all</button>
    {theme_chips}
  </div>
  <div class="archive-stats"><span id="archive-count">{len(entries)}</span> / {len(entries)} transmissions</div>
</div>
<table>
<thead><tr><th>DATE</th><th>TRANSMISSION</th></tr></thead>
<tbody id="archive-body">
{rows}
</tbody>
</table>
</article>
"""
    page = html_shell(title="archive", body=body)
    (DOCS_DIR / "archive.html").write_text(page, encoding="utf-8")


SITE_URL = "https://brianbaldock.github.io/aigregator"

# Domains where a bare URL (root path only) is almost certainly a "I couldn't
# find the deep link" placeholder rather than a real citation.
BARE_DOMAIN_BLOCKLIST = {
    "reuters.com", "www.reuters.com",
    "apnews.com", "www.apnews.com", "ap.org",
    "bloomberg.com", "www.bloomberg.com",
    "news.google.com",
    "ft.com", "www.ft.com",
    "wsj.com", "www.wsj.com",
    "nytimes.com", "www.nytimes.com",
    "cnbc.com", "www.cnbc.com",
    "techcrunch.com",
    "theverge.com", "www.theverge.com",
    "wired.com", "www.wired.com",
    "arstechnica.com",
}


def strip_bare_domain_citations(md_text: str) -> tuple[str, list[str]]:
    """Remove markdown link refs that point at bare-domain homepages.
    Returns (cleaned_md, warnings)."""
    from urllib.parse import urlparse
    warnings: list[str] = []

    def link_repl(m: re.Match) -> str:
        label, url = m.group(1), m.group(2)
        try:
            p = urlparse(url)
        except ValueError:
            return m.group(0)
        host = p.netloc.lower()
        path = p.path.strip("/")
        # Bare = no path or path is just a slash
        if host in BARE_DOMAIN_BLOCKLIST and not path:
            warnings.append(f"  bare-domain citation stripped: [{label}]({url})")
            # Replace with plain label so the sentence still reads
            return label
        return m.group(0)

    cleaned = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", link_repl, md_text)
    # Tidy up dangling ", " or "(  )" left by removed links
    cleaned = re.sub(r",\s*,", ",", cleaned)
    cleaned = re.sub(r"\(\s*,\s*", "(", cleaned)
    cleaned = re.sub(r",\s*\)", ")", cleaned)
    cleaned = re.sub(r"\(\s*\)", "", cleaned)
    return cleaned, warnings


def build_feeds(entries: list[dict]) -> None:
    """Generate RSS 2.0 feed.xml and Atom 1.0 atom.xml from digests."""
    from xml.sax.saxutils import escape as xml_escape

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    now_rfc822 = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")

    rss_items = []
    atom_entries = []
    for e in entries[:30]:
        slug, title, preview = e["slug"], e["title"], e["preview"]
        url = f"{SITE_URL}/digests/{slug}.html"
        # Use slug date as pub date (00:00 UTC of that day) — predictable, no clock drift
        try:
            pub_dt = datetime.strptime(slug, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            pub_dt = datetime.now(timezone.utc)
        pub_rfc822 = pub_dt.strftime("%a, %d %b %Y %H:%M:%S +0000")
        pub_iso = pub_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Pull article HTML for full-content feed
        digest_path = DOCS_DIGESTS / f"{slug}.html"
        article_html = ""
        if digest_path.exists():
            m = re.search(r'(<article class="digest">.*?</article>)', digest_path.read_text(encoding="utf-8"), re.DOTALL)
            if m:
                article_html = m.group(1)

        rss_items.append(f"""    <item>
      <title>{xml_escape(title)}</title>
      <link>{url}</link>
      <guid isPermaLink="true">{url}</guid>
      <pubDate>{pub_rfc822}</pubDate>
      <description>{xml_escape(preview)}</description>
      <content:encoded><![CDATA[{article_html}]]></content:encoded>
    </item>""")

        atom_entries.append(f"""  <entry>
    <title>{xml_escape(title)}</title>
    <link href="{url}"/>
    <id>{url}</id>
    <updated>{pub_iso}</updated>
    <summary>{xml_escape(preview)}</summary>
    <content type="html"><![CDATA[{article_html}]]></content>
  </entry>""")

    rss = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>AIGREGATOR</title>
    <link>{SITE_URL}/</link>
    <atom:link href="{SITE_URL}/feed.xml" rel="self" type="application/rss+xml"/>
    <description>Daily AI signal, scored and cited.</description>
    <language>en-us</language>
    <lastBuildDate>{now_rfc822}</lastBuildDate>
{chr(10).join(rss_items)}
  </channel>
</rss>
"""

    atom = f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>AIGREGATOR</title>
  <link href="{SITE_URL}/"/>
  <link rel="self" href="{SITE_URL}/atom.xml"/>
  <id>{SITE_URL}/</id>
  <updated>{now_iso}</updated>
  <subtitle>Daily AI signal, scored and cited.</subtitle>
{chr(10).join(atom_entries)}
</feed>
"""

    (DOCS_DIR / "feed.xml").write_text(rss, encoding="utf-8")
    (DOCS_DIR / "atom.xml").write_text(atom, encoding="utf-8")


def extract_digest_meta(text: str) -> dict:
    """Extract themes, top sources, and source diversity from a digest's markdown."""
    from collections import Counter
    from urllib.parse import urlparse

    # Themes from "🏷️ tag1, tag2, tag3" inline markers
    themes: Counter = Counter()
    for m in re.finditer(r"🏷️\s*([a-z0-9, \-]+?)(?=\s+\*\*|\s+_|\s*$)", text, re.MULTILINE):
        for t in re.split(r",\s*", m.group(1).strip()):
            t = t.strip()
            if t and len(t) < 30:
                themes[t] += 1

    # Source domains from markdown links
    sources: Counter = Counter()
    for m in re.finditer(r"\]\((https?://[^)]+)\)", text):
        try:
            host = urlparse(m.group(1)).netloc.lower().lstrip("www.")
            if host and "." in host:
                sources[host] += 1
        except ValueError:
            continue

    total_links = sum(sources.values())
    top_share = (sources.most_common(1)[0][1] / total_links * 100) if total_links else 0
    diversity_warn = top_share > 40 and total_links >= 5

    # Story titles from TL;DR (bold inside ordered list items at top)
    tldr = []
    ol_match = re.search(r"## ⚡ TL;DR\s*\n(.*?)(?=\n## )", text, re.DOTALL)
    if ol_match:
        for line in ol_match.group(1).split("\n"):
            tm = re.search(r"\*\*([^*]+)\*\*", line)
            if tm:
                tldr.append(tm.group(1).strip().rstrip("."))

    return {
        "themes": dict(themes.most_common(10)),
        "sources": dict(sources.most_common(10)),
        "top_source_share": round(top_share, 1),
        "diversity_warn": diversity_warn,
        "total_sources": len(sources),
        "total_links": total_links,
        "tldr": tldr,
    }


def build_sitemap(entries: list[dict]) -> None:
    """Generate sitemap.xml + robots.txt."""
    from xml.sax.saxutils import escape as xml_escape
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    urls = [
        (f"{SITE_URL}/", today, "daily", "1.0"),
        (f"{SITE_URL}/archive.html", today, "daily", "0.8"),
        (f"{SITE_URL}/about.html", today, "monthly", "0.5"),
    ]
    for e in entries:
        urls.append((f"{SITE_URL}/digests/{e['slug']}.html", e["slug"], "never", "0.7"))
    body = "\n".join(
        f"  <url><loc>{xml_escape(u)}</loc><lastmod>{lm}</lastmod>"
        f"<changefreq>{cf}</changefreq><priority>{pr}</priority></url>"
        for u, lm, cf, pr in urls
    )
    sitemap = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{body}
</urlset>
"""
    (DOCS_DIR / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    (DOCS_DIR / "robots.txt").write_text(
        f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n",
        encoding="utf-8",
    )


def build_404() -> None:
    """Custom 404 in the AIgregator terminal aesthetic."""
    body = """
<article class="digest" style="text-align:center;">
<pre class="ascii" style="color:var(--magenta);text-shadow:0 0 8px var(--magenta);font-size:14px;line-height:1.2;">
  ╔══════════════════════════════════════╗
  ║   ERR 404 :: SIGNAL LOST             ║
  ║   PACKET NOT FOUND IN UPLINK QUEUE   ║
  ╚══════════════════════════════════════╝
</pre>
<p style="color:var(--amber);font-size:18px;margin-top:24px;">
&gt; traceroute target.unknown<br>
&gt; hop 01 ... <span style="color:var(--green)">aigregator.gw</span> ... 12ms<br>
&gt; hop 02 ... <span style="color:var(--green)">net.transit</span> ... 28ms<br>
&gt; hop 03 ... <span style="color:var(--cyan)">??.??.??.??</span> ... <span style="color:var(--red)">* * *</span><br>
&gt; hop 04 ... <span style="color:var(--red)">DESTINATION UNREACHABLE</span>
</p>
<p style="margin-top:24px;">
The transmission you requested either never existed or has decayed into the noise floor.
</p>
<p style="margin-top:16px;">
[ <a href="/">RETURN TO LATEST</a> ] &nbsp; [ <a href="/archive.html">BROWSE ARCHIVE</a> ]
</p>
</article>
"""
    page = html_shell(title="404", body=body)
    (DOCS_DIR / "404.html").write_text(page, encoding="utf-8")


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
    for src, dst in CSS_FILES + JS_FILES:
        if src.exists():
            shutil.copy2(src, dst)
    # Ensure no Jekyll
    (DOCS_DIR / ".nojekyll").touch()

    entries = build_digest_pages()
    build_index(entries)
    build_archive(entries)
    build_about()
    build_404()
    build_feeds(entries)
    build_sitemap(entries)
    print(f"built {len(entries)} digest page(s) + feeds + sitemap + 404")
    return 0


if __name__ == "__main__":
    sys.exit(main())
