#!/usr/bin/env python3
"""hn.py — Hacker News front-page + recent AI stories via Algolia. Writes hn_items.json.

Ported from proven /tmp/aig/fetch_hn.py (2026-07-22) onto the _common contract.
"""
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import out_path, atomic_write_json, get, log  # noqa: E402

NOW = datetime.now(timezone.utc)
CUTOFF_TS = int((NOW - timedelta(hours=30)).timestamp())

AI_RE = ("ai", "llm", "gpt", "claude", "gemini", "anthropic", "openai", "deepmind",
         "mistral", "llama", "model", "neural", "agent", "transformer", "diffusion",
         "inference", "machine learning", "ml ", "rag", "embedding", "fine-tun",
         "prompt", "chatbot", "nvidia", "hugging", "grok", "reasoning")


def is_ai(title):
    low = (title or "").lower()
    return any(k in low for k in AI_RE)


def main():
    out, seen = [], set()
    urls = [
        "https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=50",
        ("https://hn.algolia.com/api/v1/search_by_date?tags=story&numericFilters="
         f"created_at_i>{CUTOFF_TS},points>30&hitsPerPage=100"),
    ]
    for url in urls:
        try:
            d = json.loads(get(url, timeout=20))
        except Exception as ex:
            log(f"ERR={str(ex)[:70]}")
            time.sleep(2)
            continue
        for h in d.get("hits", []):
            title = h.get("title") or ""
            oid = h.get("objectID", "")
            if not title or oid in seen or not is_ai(title):
                continue
            points = h.get("points", 0) or 0
            if points < 30:
                continue
            url_link = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"
            created = h.get("created_at", "")
            out.append({
                "title": title, "url": url_link, "summary": "",
                "points": points, "num_comments": h.get("num_comments", 0),
                "created_at": created, "published": created,
                "hn_url": f"https://news.ycombinator.com/item?id={oid}",
            })
            seen.add(oid)
        time.sleep(1)
    out.sort(key=lambda x: -x["points"])
    atomic_write_json(out_path("hn_items.json"), out)
    log(f"wrote {len(out)} AI items")


if __name__ == "__main__":
    main()
