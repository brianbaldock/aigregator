#!/usr/bin/env python3
"""rss.py — pull all feeds from feeds.txt, keep last ~26h. Writes rss_items.json.

Ported from the proven /tmp/aig/fetch_rss.py (2026-07-22) onto the committed
_common contract: writes into AIG_RUN_DIR via atomic_write_json.
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from email.utils import parsedate_to_datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import out_path, atomic_write_json, get, log  # noqa: E402

FEEDS = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "feeds.txt",
)
NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(hours=26)


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        return parsedate_to_datetime(s)
    except Exception:
        pass
    for f in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            d = datetime.strptime(s, f)
            return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None


def strip_html(t):
    if not t:
        return ""
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", t).strip()[:500]


def main():
    feeds = []
    for line in open(FEEDS):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) >= 3:
            feeds.append((parts[0], parts[1], int(parts[2])))

    items = []
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    for name, url, cred in feeds:
        try:
            root = ET.fromstring(get(url, timeout=20))
        except Exception as e:
            log(f"  {name}: FAIL {str(e)[:70]}")
            continue
        entries = root.findall(".//item")
        atom = False
        if not entries:
            entries = root.findall(".//atom:entry", ns)
            atom = True
        cnt = 0
        for e in entries:
            if atom:
                title = e.findtext("atom:title", "", ns)
                link_el = e.find("atom:link", ns)
                link = link_el.get("href") if link_el is not None else ""
                desc = e.findtext("atom:summary", "", ns) or ""
                pub = (e.findtext("atom:published", "", ns)
                       or e.findtext("atom:updated", "", ns))
            else:
                title = e.findtext("title", "")
                link = e.findtext("link", "")
                desc = e.findtext("description", "") or ""
                pub = e.findtext("pubDate", "")
            d = parse_date(pub)
            if d and d < CUTOFF:
                continue
            title = strip_html(title)
            if not title or not link:
                continue
            items.append({"source": name, "credibility": cred, "title": title,
                          "url": link.strip(), "summary": strip_html(desc),
                          "published": d.isoformat() if d else None})
            cnt += 1
        log(f"  {name}: {cnt} recent")

    atomic_write_json(out_path("rss_items.json"), items)
    log(f"TOTAL rss items: {len(items)}")


if __name__ == "__main__":
    main()
