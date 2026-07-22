#!/usr/bin/env python3
"""arxiv.py — cs.AI/cs.LG/cs.CL/cs.CY, RSS primary, API fallback. Writes arxiv_items.json.

Ported from myarxiv.py (2026-07-22), which fixed a broken predecessor that only
PARSED pre-existing XML and never fetched. RSS is the fast path (no rate limit);
API fallback per-category with spacing if RSS is empty (weekends).
"""
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import out_path, atomic_write_json, get, log  # noqa: E402

NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(hours=48)
CATS = ["cs.AI", "cs.LG", "cs.CL", "cs.CY"]


def strip_html(t):
    if not t:
        return ""
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()[:600]


def main():
    items, seen = [], set()

    def add(cat, title, link, desc, dt):
        if not title or not link or link in seen:
            return False
        seen.add(link)
        items.append({"source": f"arXiv:{cat}", "credibility": 4, "category": cat,
                      "title": title, "url": link, "summary": desc,
                      "published": dt.isoformat() if dt else None})
        return True

    for cat in CATS:
        got = 0
        # PRIMARY: RSS
        try:
            root = ET.fromstring(get(f"https://rss.arxiv.org/rss/{cat}", timeout=20))
            for it in root.findall(".//item"):
                title = strip_html(it.findtext("title", ""))
                link = (it.findtext("link", "") or "").strip()
                desc = strip_html(it.findtext("description", ""))
                pub = it.findtext("pubDate", "")
                try:
                    d = parsedate_to_datetime(pub) if pub else None
                except Exception:
                    d = None
                if d and d < CUTOFF:
                    continue
                if add(cat, title, link, desc, d):
                    got += 1
            log(f"  {cat}: RSS {got}")
        except Exception as e:
            log(f"  {cat}: RSS FAIL {str(e)[:50]}")
        # FALLBACK: API if RSS empty
        if got == 0:
            for attempt in (1, 2, 3):
                try:
                    api = ("https://export.arxiv.org/api/query?search_query=cat:"
                           f"{cat}&max_results=25&sortBy=submittedDate&sortOrder=descending")
                    ns = {"a": "http://www.w3.org/2005/Atom"}
                    root = ET.fromstring(get(api, timeout=30))
                    entries = root.findall("a:entry", ns)
                    if not entries:
                        time.sleep(5)
                        continue
                    for e in entries:
                        title = strip_html(e.findtext("a:title", "", ns))
                        link = (e.findtext("a:id", "", ns) or "").strip()
                        desc = strip_html(e.findtext("a:summary", "", ns))
                        pubs = e.findtext("a:published", "", ns)
                        try:
                            d = (datetime.fromisoformat(pubs.replace("Z", "+00:00"))
                                 if pubs else None)
                        except Exception:
                            d = None
                        if d and d < CUTOFF:
                            continue
                        if add(cat, title, link, desc, d):
                            got += 1
                    log(f"  {cat}: API {got}")
                    break
                except Exception as e:
                    log(f"  {cat}: API try{attempt} FAIL {str(e)[:50]}")
                    time.sleep(5)
        time.sleep(4)  # polite gap between categories

    atomic_write_json(out_path("arxiv_items.json"), items)
    log(f"TOTAL arxiv items: {len(items)}")


if __name__ == "__main__":
    main()
