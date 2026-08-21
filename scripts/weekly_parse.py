#!/usr/bin/env python3
"""
weekly_parse.py — deterministic parser for AIgregator daily digest markdown.

No LLM. Turns digests/YYYY-MM-DD.md into structured records so the weekly
roundup can be assembled from facts instead of re-read as prose by a model.

The digest format (written by write_digest.py) is stable:

    # 2026-08-18 :: AI DAILY DIGEST

    _subtitle_

    > **📊 TODAY:** 29 stories · 15 sources · 🟡 +0.0 sentiment · ...

    ## ⚡ TL;DR
    1. 20 🔥 🟡 **Headline.** Blurb. ([Src](url), [Src2](url2))

    ## 🧠 Models & Releases
    _5 items · 🟡 +0.0 sentiment_
    - 14 🔥 🟡 ▤×3 🏷️ training **Headline.** Summary. Sources: [Src](url), ...

Public API:
    parse_digest(path) -> DigestDay
    parse_all(paths)   -> list[DigestDay]
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import os
import re
from typing import Iterable

# ---------------------------------------------------------------------------
# Regexes. Kept narrow on purpose: a shape change in write_digest.py should
# make this parser return LESS, loudly, rather than silently mis-parse.
# ---------------------------------------------------------------------------

RE_H1_DATE = re.compile(r"^#\s+(\d{4}-\d{2}-\d{2})\s*::", re.M)
RE_SECTION = re.compile(r"^##\s+(.+?)\s*$", re.M)
RE_MD_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
RE_TLDR_ITEM = re.compile(r"^(\d+)\.\s+(.*)$")
RE_BULLET_ITEM = re.compile(r"^-\s+(.*)$")
# **Headline.** — the first bold run on the line is the headline.
RE_BOLD_HEAD = re.compile(r"\*\*(.+?)\*\*")
RE_STAT_STORIES = re.compile(r"(\d+)\s+stories")
RE_STAT_SOURCES = re.compile(r"(\d+)\s+sources")
RE_CROSS = re.compile(r"(\d+)\s+cross-source")
RE_THEMES = re.compile(r"🏷️\s*([a-z, ]+?)(?=\s*\*\*)")
RE_SENTIMENT = re.compile(r"([🟢🟡🔴])")

# Section heading -> canonical slug. Emoji are stripped before lookup.
SECTION_SLUGS = {
    "tl;dr": "tldr",
    "models & releases": "models",
    "research": "research",
    "responsible ai, safety & policy": "safety",
    "safety & policy": "safety",
    "funding & business": "funding",
    "tools & libraries": "tools",
    "open source": "opensource",
    "projects & demos": "projects",
    "discourse": "discourse",
    "from the community": "discourse",
}

# Hub / landing pages that are never a real story. Matched as substrings
# against the URL. Kept here rather than in the clusterer because it is a
# property of the SOURCE, not of the clustering.
HUB_URL_MARKERS = (
    "anthropic.com/news",          # bare newsroom index (exact-match guarded below)
    "bloomberg.com/technology",
    "reuters.com/technology/artificial-intelligence",
)
# Exact URLs that are always hubs, no matter what title is attached.
HUB_URL_EXACT = {
    "https://www.anthropic.com/news",
    "https://www.anthropic.com/news/",
    "https://openai.com/news",
    "https://openai.com/blog",
}
HUB_TITLE_MARKERS = (
    "newsroom",
    "at a glance",
    "artificial intelligence news",
    "bloomberg technology",
    "ai - bloomberg",
    "latest news",
)


@dataclasses.dataclass
class DigestItem:
    """One story as it appeared in one day's digest."""
    date: str                    # YYYY-MM-DD of the digest it appeared in
    section: str                 # canonical section slug
    headline: str
    summary: str
    urls: list[str]              # every cited URL, in document order
    sources: list[str]           # display names, parallel to urls
    themes: list[str]
    score: int | None
    sentiment: str               # 🟢 / 🟡 / 🔴 / ""
    in_tldr: bool
    tldr_rank: int | None

    @property
    def canonical_url(self) -> str:
        return self.urls[0] if self.urls else ""

    @property
    def is_hub(self) -> bool:
        """True if this item is a vendor landing page rather than a story."""
        for u in self.urls:
            if u.rstrip("/") in {h.rstrip("/") for h in HUB_URL_EXACT}:
                return True
        low = self.headline.lower()
        if any(m in low for m in HUB_TITLE_MARKERS):
            return True
        return False


@dataclasses.dataclass
class DigestDay:
    """One parsed daily digest."""
    date: str
    path: str
    subtitle: str
    items: list[DigestItem]
    stat_stories: int | None
    stat_sources: int | None
    stat_cross: int | None

    @property
    def date_obj(self) -> dt.date:
        return dt.date.fromisoformat(self.date)


def _slugify_section(heading: str) -> str:
    """Strip emoji/punctuation from a '## ...' heading and map to a slug."""
    cleaned = "".join(c for c in heading if c.isascii()).strip()
    cleaned = cleaned.strip(" :").lower()
    if cleaned in SECTION_SLUGS:
        return SECTION_SLUGS[cleaned]
    # Fall back to a normalized form so an unknown section is still grouped
    # consistently rather than silently dropped.
    return re.sub(r"[^a-z0-9]+", "-", cleaned).strip("-") or "unknown"


def _split_head_and_summary(body: str) -> tuple[str, str]:
    """Pull the bold headline out of an item line, return (headline, summary)."""
    m = RE_BOLD_HEAD.search(body)
    if not m:
        return "", body.strip()
    headline = m.group(1).strip().rstrip(".")
    summary = body[m.end():]
    # Trim the trailing citation block, which the caller extracts separately.
    summary = re.split(r"\s*(?:Sources:|\()\s*\[", summary)[0]
    return headline, summary.strip()


def _parse_item_line(line: str, date: str, section: str,
                     tldr_rank: int | None) -> DigestItem | None:
    """Parse one TL;DR or bullet line into a DigestItem."""
    body = line.strip()
    if not body:
        return None

    score = None
    m_score = re.match(r"^(\d+)\s", body)
    if m_score:
        score = int(m_score.group(1))
        body = body[m_score.end():]

    sentiment = ""
    m_sent = RE_SENTIMENT.search(body[:24])
    if m_sent:
        sentiment = m_sent.group(1)

    themes: list[str] = []
    m_themes = RE_THEMES.search(body)
    if m_themes:
        themes = [t.strip() for t in m_themes.group(1).split(",") if t.strip()]

    links = RE_MD_LINK.findall(body)
    urls = [u for _, u in links]
    sources = [s for s, _ in links]

    headline, summary = _split_head_and_summary(body)
    if not headline:
        return None

    return DigestItem(
        date=date,
        section=section,
        headline=headline,
        summary=summary,
        urls=urls,
        sources=sources,
        themes=themes,
        score=score,
        sentiment=sentiment,
        in_tldr=tldr_rank is not None,
        tldr_rank=tldr_rank,
    )


def parse_digest(path: str) -> DigestDay:
    """Parse one digests/YYYY-MM-DD.md into a DigestDay. Never raises on a
    malformed body; returns whatever parsed cleanly so a single bad day cannot
    take down the weekly run."""
    text = open(path, encoding="utf-8").read()

    m_date = RE_H1_DATE.search(text)
    if m_date:
        date = m_date.group(1)
    else:
        # Fall back to the filename, which is authoritative for the archive.
        date = os.path.basename(path).replace(".md", "")

    subtitle = ""
    m_sub = re.search(r"^_(.+?)_\s*$", text, re.M)
    if m_sub:
        subtitle = m_sub.group(1).strip()

    def _stat(rx):
        m = rx.search(text)
        return int(m.group(1)) if m else None

    items: list[DigestItem] = []
    current_section = "unknown"
    tldr_counter = 0

    for line in text.splitlines():
        m_sec = RE_SECTION.match(line)
        if m_sec:
            current_section = _slugify_section(m_sec.group(1))
            continue

        if current_section == "tldr":
            m_t = RE_TLDR_ITEM.match(line.strip())
            if m_t:
                tldr_counter += 1
                it = _parse_item_line(m_t.group(2), date, "tldr", tldr_counter)
                if it:
                    items.append(it)
                continue

        m_b = RE_BULLET_ITEM.match(line.strip())
        if m_b:
            it = _parse_item_line(m_b.group(1), date, current_section, None)
            if it:
                items.append(it)

    return DigestDay(
        date=date,
        path=path,
        subtitle=subtitle,
        items=items,
        stat_stories=_stat(RE_STAT_STORIES),
        stat_sources=_stat(RE_STAT_SOURCES),
        stat_cross=_stat(RE_CROSS),
    )


def parse_all(paths: Iterable[str]) -> list[DigestDay]:
    days = [parse_digest(p) for p in paths]
    return sorted(days, key=lambda d: d.date)


if __name__ == "__main__":
    import sys, json
    for p in sys.argv[1:]:
        d = parse_digest(p)
        tldr = sum(1 for i in d.items if i.in_tldr)
        hubs = sum(1 for i in d.items if i.is_hub)
        print(f"{d.date}  items={len(d.items):3d}  tldr={tldr}  hubs={hubs}  "
              f"stats={d.stat_stories}/{d.stat_sources}")
