"""Agent-facing surfaces: per-story JSON Feed + llms.txt.

Parses digests/*.md (the source of truth) into individual stories so agents
get structured items with source URLs attached instead of scraping HTML.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"
FEED_DAYS = 7

SKIP_SECTIONS = {"tldr", "prediction-markets"}
_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_SCORED = re.compile(
    r"^-\s+(?P<score>\d+)\s+(?P<pre>.*?)\*\*(?P<title>.+?)\*\*\s*(?P<rest>.*)$"
)


def section_anchor(heading: str) -> str:
    """Mirror build.render_digest_md heading_id() so links land on the section.

    heading_id() runs on rendered HTML, so '&' is '&amp;' there (-> 'amp').
    """
    from html import escape
    plain = re.sub(r"[^\w\s-]", "", escape(heading, quote=False)).strip().lower()
    return re.sub(r"[\s_]+", "-", plain)[:48]


def section_key(heading: str) -> str:
    plain = re.sub(r"[^\w\s&-]", "", heading).strip().lower()
    table = {
        "tldr": "tldr", "models & releases": "models", "research": "research",
        "responsible ai safety & policy": "safety",
        "cool projects & novel applications": "projects",
        "industry & funding": "funding", "tools & demos": "tools",
        "open source & emerging": "opensource",
        "prediction markets": "prediction-markets", "discourse": "discourse",
    }
    plain = re.sub(r"\s+", " ", plain.replace(",", ""))
    return table.get(plain, re.sub(r"[^a-z0-9]+", "-", plain).strip("-"))


def parse_stories(md: str, slug: str, site_url: str) -> list[dict]:
    stories: list[dict] = []
    heading = key = ""
    for line in md.splitlines():
        if line.startswith("## "):
            heading = line[3:].strip()
            key = section_key(heading)
            continue
        if not line.startswith("- ") or not key or key in SKIP_SECTIONS:
            continue
        url_base = f"{site_url}/digests/{slug}.html#{section_anchor(heading)}"
        m = _SCORED.match(line)
        if m:
            rest = m.group("rest")
            src_part = ""
            if "Sources:" in rest:
                rest, src_part = rest.rsplit("Sources:", 1)
            pre = m.group("pre")
            cross = re.search(r"▤×(\d+)", pre)
            themes = re.search(r"🏷️\s*([\w\s,-]+?)\s*$", pre)
            sources = [{"name": n, "url": u} for n, u in _LINK.findall(src_part)]
            if not sources:
                continue
            stories.append({
                "title": m.group("title").strip().rstrip("."),
                "summary": _LINK.sub(r"\1", rest).strip(),
                "section": key,
                "score": int(m.group("score")),
                "source_count": int(cross.group(1)) if cross else len(sources),
                "themes": [t.strip() for t in themes.group(1).split(",") if t.strip()] if themes else [],
                "sources": sources,
                "edition": slug,
                "edition_url": url_base,
            })
            continue
        links = _LINK.findall(line)
        if key == "discourse" and links:
            label, url = links[0]
            note = _LINK.sub("", line[2:]).strip()
            # Bluesky/HN rows use a handle or "HN" as link text; the real
            # title is the prose that follows.
            if label.startswith("@") or label.strip() == "HN":
                title, summary = note, f"via {label.strip()}"
            else:
                title, summary = label.strip(), note
            stories.append({
                "title": title, "summary": summary, "section": key,
                "score": None, "source_count": 1, "themes": [],
                "sources": [{"name": re.sub(r"^www\.", "", url.split("/")[2]), "url": url}],
                "edition": slug, "edition_url": url_base,
            })
    return stories


def build_json_feed(digests_dir: Path, out: Path, site_url: str, days: int = FEED_DAYS) -> int:
    files = sorted(digests_dir.glob("*.md"), reverse=True)[:days]
    items = []
    for f in files:
        slug = f.stem
        for i, s in enumerate(parse_stories(f.read_text(encoding="utf-8"), slug, site_url), 1):
            src_line = "Sources: " + ", ".join(f"{x['name']} {x['url']}" for x in s["sources"])
            items.append({
                "id": f"{site_url}/digests/{slug}.html#item-{i}",
                "url": s["edition_url"],
                "external_url": s["sources"][0]["url"],
                "title": s["title"],
                "content_text": f"{s['summary']}\n\n{src_line}".strip(),
                "summary": s["summary"],
                "date_published": f"{slug}T14:00:00Z",
                "tags": s["themes"],
                "_aigregator": {k: s[k] for k in ("section", "score", "source_count", "sources", "edition")},
            })
    feed = {
        "version": "https://jsonfeed.org/version/1.1",
        "title": "AIgregator: AI news, one item per story",
        "home_page_url": f"{site_url}/",
        "feed_url": f"{site_url}/feed.json",
        "description": (
            "Per-story feed of the AIgregator daily AI digest, last "
            f"{days} editions. Summaries CC BY 4.0 ({LICENSE_URL}); credit "
            "AIgregator (aigregator.news). Linked articles belong to their "
            "publishers and are not covered. Read and cite the source; it is authoritative."
        ),
        "language": "en",
        "authors": [{"name": "AIgregator", "url": f"{site_url}/about.html"}],
        "_aigregator": {
            "license": "CC-BY-4.0", "license_url": LICENSE_URL,
            "updated": "daily ~14:00 UTC", "docs": f"{site_url}/llms.txt",
            "score_note": "score and source_count are AIgregator's own ranking; source_count counts outlets, not verified facts",
        },
        "items": items,
    }
    out.write_text(json.dumps(feed, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(items)


def llms_txt(site_url: str) -> str:
    return f"""# AIgregator

> Daily AI news digest. Each morning we gather AI news from wires, lab blogs,
> arXiv, GitHub, Hugging Face and social sources, cluster duplicate coverage,
> score it, and write short summaries that link to the original reporting.
> We point you to the right source; the source is the authority.

## Feeds for agents

- [Per-story JSON Feed]({site_url}/feed.json): JSON Feed 1.1, one item per story, last {FEED_DAYS} editions. Each item has title, our summary, section, themes, score, source_count and the original source URLs. Use this first.
- [RSS]({site_url}/feed.xml) / [Atom]({site_url}/atom.xml): one item per daily edition, full HTML, last 30 editions.
- [Weekly roundup RSS]({site_url}/weekly/feed.xml)
- [Archive index]({site_url}/archive.json): every edition with slug, title, themes and top source domains.
- [Sitemap]({site_url}/sitemap.xml)

Edition URLs follow `{site_url}/digests/YYYY-MM-DD.html`.

## How to use it well

- A new edition publishes once a day around 14:00 UTC. Fetch once a day after that. Use conditional requests (ETag / If-Modified-Since); do not poll every few minutes.
- Cite the original source for facts. Cite AIgregator for our synthesis: the summary wording, grouping, scores and selection.
- `score` and `source_count` are our own ranking. `source_count` counts distinct outlets that covered a story; it is not independent fact-checking.
- Summaries are machine-assisted and curated, and may contain errors. When it matters, read the linked article.

## License

- AIgregator's headlines, summaries, scores and editorial organization: CC BY 4.0 ({LICENSE_URL}). Credit "AIgregator (aigregator.news)" and link to the edition or story.
- Linked articles belong to their publishers and are not covered by this license. Read and cite them at the source.
- Prediction-market data is from Polymarket and remains subject to its terms.
- Site code is MIT-licensed: https://github.com/brianbaldock/AIgregator

## About

- [About and methodology]({site_url}/about.html)
"""
