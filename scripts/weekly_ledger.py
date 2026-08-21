#!/usr/bin/env python3
"""
weekly_ledger.py — deterministic cross-week provenance for the AIgregator
weekly roundup. No LLM.

Answers two questions the weekly roundup could not previously answer:

  1. "Is this story actually NEW this week, or are we re-reporting something
     from July?"  (Defect A: stale content laundering, weekly/2026-W34.md)
  2. "How does this week's story connect to what we said LAST week?"
     (continuity across roundups, so the site reads as one evolving story)

Design decisions forced by the cross-model design review (gpt-5.6-terra +
grok-4.6, both via Copilot CLI, 2026-08-21):

  - First-seen is computed by URL identity BEFORE any clustering. Both ducks
    flagged that clustering first, then taking a cluster's oldest URL, lets one
    stale member poison a genuinely new story ("first-seen poisoning").
  - Hard-dropping every pre-window story is editorially wrong. A story can
    legitimately develop for weeks. Classification is four-way, not binary.
  - The archive parser must accept BOTH citation shapes ("Sources: [x](u)" and
    the TL;DR "([x](u))" form) or first_seen skews young and the gate silently
    under-reports staleness.
"""
from __future__ import annotations

import dataclasses
import datetime as dt
import glob
import os
import re
from collections import defaultdict

from weekly_parse import DigestDay, DigestItem, parse_digest, parse_all

# --- Classification ---------------------------------------------------------
# NEW      every URL in the story first appeared inside the window
# DELTA    the story predates the window BUT has fresh reporting this week
# HUM      entirely pre-window, but still being covered most days
# REPRINT  entirely pre-window, sporadic. This is the W34 Anthropic failure.
CLASS_NEW = "new"
CLASS_DELTA = "delta"
CLASS_HUM = "hum"
CLASS_REPRINT = "reprint"

# A pre-window story must appear on at least this many distinct days in the
# window to count as "still running" rather than a sporadic reprint.
HUM_MIN_DAYS = 4

# At most this many DELTA stories may occupy prime editorial slots, so the
# roundup cannot degenerate into a wall of "ongoing" labels.
MAX_DELTA_IN_TOP = 2


def normalize_url(url: str) -> str:
    """Canonical form for identity comparison.

    Deliberately conservative: strips tracking params, trailing slash, scheme,
    and www, but does NOT attempt cross-outlet identity. Two outlets covering
    one event stay distinct here; that is the clusterer's job, not the
    ledger's."""
    u = url.strip()
    u = re.sub(r"^https?://", "", u)
    u = re.sub(r"^www\.", "", u)
    u = u.split("#")[0]
    # Drop tracking/syndication query params but keep meaningful ones.
    if "?" in u:
        base, _, qs = u.partition("?")
        keep = []
        for part in qs.split("&"):
            k = part.split("=")[0].lower()
            if k.startswith(("utm_", "at_", "syn-", "ref", "src")):
                continue
            if k in {"campaign", "medium", "fbclid", "gclid"}:
                continue
            keep.append(part)
        u = base + ("?" + "&".join(keep) if keep else "")
    return u.rstrip("/").lower()


@dataclasses.dataclass
class UrlRecord:
    """Everywhere one URL has ever appeared across the digest archive."""
    url: str
    normalized: str
    first_seen: str              # YYYY-MM-DD of earliest digest
    last_seen: str
    all_dates: list[str]
    headlines: list[str]

    def days_in_window(self, start: str, end: str) -> list[str]:
        return [d for d in self.all_dates if start <= d <= end]


def build_url_ledger(digest_paths: list[str]) -> dict[str, UrlRecord]:
    """Scan the ENTIRE digest archive and record when each URL first appeared.

    This is the bootstrap/authority for historical data. Terra correctly noted
    that the durable long-term fix is for the daily pipeline to persist event
    provenance at write time; until that exists, the archive scan is the only
    source of truth for the 100+ digests already published.
    """
    ledger: dict[str, UrlRecord] = {}
    for path in sorted(digest_paths):
        day = parse_digest(path)
        for item in day.items:
            for url in item.urls:
                norm = normalize_url(url)
                if not norm:
                    continue
                rec = ledger.get(norm)
                if rec is None:
                    ledger[norm] = UrlRecord(
                        url=url, normalized=norm,
                        first_seen=day.date, last_seen=day.date,
                        all_dates=[day.date], headlines=[item.headline],
                    )
                else:
                    if day.date < rec.first_seen:
                        rec.first_seen = day.date
                    if day.date > rec.last_seen:
                        rec.last_seen = day.date
                    if day.date not in rec.all_dates:
                        rec.all_dates.append(day.date)
                    if item.headline not in rec.headlines:
                        rec.headlines.append(item.headline)
    for rec in ledger.values():
        rec.all_dates.sort()
    return ledger


def classify(urls: list[str], window_start: str, window_end: str,
             ledger: dict[str, UrlRecord]) -> tuple[str, dict]:
    """Classify a story by the provenance of ALL its cited URLs.

    Returns (class, evidence) where evidence explains the decision so the
    renderer can cite it and a test can assert on it. Never returns a bare
    verdict: an unexplainable classification is an untestable one.
    """
    fresh, stale = [], []
    day_hits: set[str] = set()
    earliest = None

    for url in urls:
        norm = normalize_url(url)
        rec = ledger.get(norm)
        if rec is None:
            # Never seen in the archive at all: it is new by definition.
            fresh.append(url)
            continue
        if earliest is None or rec.first_seen < earliest:
            earliest = rec.first_seen
        day_hits.update(rec.days_in_window(window_start, window_end))
        if rec.first_seen >= window_start:
            fresh.append(url)
        else:
            stale.append(url)

    evidence = {
        "fresh_urls": fresh,
        "stale_urls": stale,
        "first_seen": earliest,
        "days_in_window": sorted(day_hits),
    }

    if not stale:
        return CLASS_NEW, evidence
    if fresh:
        return CLASS_DELTA, evidence
    if len(day_hits) >= HUM_MIN_DAYS:
        return CLASS_HUM, evidence
    return CLASS_REPRINT, evidence


# --- Continuity with previous roundups --------------------------------------

RE_WEEKLY_LINK = re.compile(r"\[([^\]]+)\]\((https?://[^\s)]+)\)")
RE_WEEKLY_H1 = re.compile(r"^#\s+(.+?)\s*$", re.M)


@dataclasses.dataclass
class PriorWeek:
    slug: str
    path: str
    title: str
    urls: set[str]               # normalized
    headline_text: str           # full body, for theme phrase matching


def load_prior_weeks(weekly_dir: str, before_slug: str,
                     limit: int = 4) -> list[PriorWeek]:
    """Load the N most recent weekly roundups preceding `before_slug`.

    Used to answer "did we already talk about this last week, and what did we
    say?" so an evolving story can be reported as evolving, with a citation
    back to the earlier roundup, rather than presented cold every Thursday.
    """
    paths = sorted(glob.glob(os.path.join(weekly_dir, "*.md")))
    out: list[PriorWeek] = []
    for p in paths:
        slug = os.path.basename(p).replace(".md", "")
        if slug >= before_slug:
            continue
        text = open(p, encoding="utf-8").read()
        m = RE_WEEKLY_H1.search(text)
        urls = {normalize_url(u) for _, u in RE_WEEKLY_LINK.findall(text)}
        out.append(PriorWeek(
            slug=slug, path=p,
            title=(m.group(1).strip() if m else slug),
            urls=urls, headline_text=text,
        ))
    return out[-limit:]


def continuity_for(urls: list[str], priors: list[PriorWeek]) -> list[dict]:
    """Which prior roundups already cited any of these URLs.

    Returns newest-first so the renderer can say "we covered this in W33"
    and link it. URL identity only: a shared URL is proof we covered it,
    whereas a shared token is merely a guess.
    """
    hits = []
    norms = {normalize_url(u) for u in urls}
    for pw in reversed(priors):
        shared = norms & pw.urls
        if shared:
            hits.append({
                "slug": pw.slug,
                "title": pw.title,
                "shared_urls": sorted(shared),
                "url": f"https://aigregator.news/weekly/{pw.slug}.html",
            })
    return hits


def window_from_digests(paths: list[str]) -> tuple[str, str]:
    """Derive the ACTUAL date window from the selected digest files.

    Defect B fix. The window is whatever the digests say it is, never what an
    ISO-week helper says it should be. Computing the expected value with the
    same helper that produced the bug is how a range test silently passes.
    """
    dates = sorted(os.path.basename(p).replace(".md", "") for p in paths)
    if not dates:
        raise ValueError("no digests selected; cannot derive a window")
    return dates[0], dates[-1]


def format_window_title(start: str, end: str) -> str:
    a = dt.date.fromisoformat(start)
    b = dt.date.fromisoformat(end)
    return f"{a.strftime('%b %-d')} – {b.strftime('%b %-d')}"


if __name__ == "__main__":
    import sys, json
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    all_digests = sorted(glob.glob(os.path.join(repo, "digests", "*.md")))
    window = sys.argv[1:] or all_digests[-7:]
    start, end = window_from_digests(window)
    print(f"window: {start} .. {end}  ({format_window_title(start, end)})")
    ledger = build_url_ledger(all_digests)
    print(f"ledger: {len(ledger)} unique URLs across {len(all_digests)} digests")

    days = parse_all(window)
    counts = defaultdict(int)
    examples = defaultdict(list)
    seen_norm = set()
    for d in days:
        for it in d.items:
            if it.is_hub or not it.urls:
                continue
            key = normalize_url(it.canonical_url)
            if key in seen_norm:
                continue
            seen_norm.add(key)
            cls, ev = classify(it.urls, start, end, ledger)
            counts[cls] += 1
            if len(examples[cls]) < 4:
                examples[cls].append((it.headline[:58], ev["first_seen"]))
    for cls in (CLASS_NEW, CLASS_DELTA, CLASS_HUM, CLASS_REPRINT):
        print(f"\n{cls.upper():8s} {counts[cls]:3d}")
        for h, fs in examples[cls]:
            print(f"    {fs}  {h}")
