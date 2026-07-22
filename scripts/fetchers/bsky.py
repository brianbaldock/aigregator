#!/usr/bin/env python3
"""bsky.py — Bluesky AI posts via public AppView searchPosts. Writes bsky_items.json.

Combines fetch + parse into one committed fetcher (the /tmp/aig split had a
path-mismatch bug: fetch wrote agg/bsky_*.json but parse read a nonexistent
bsky/q*.json). Builds share URL from the EXACT posts[].uri rkey (never fabricate)
per the hallucinated-rkey pitfall.
"""
import json
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import out_path, atomic_write_json, get, log  # noqa: E402

NOW = datetime.now(timezone.utc)
CUTOFF = NOW - timedelta(hours=24)
TERMS = ["LLM", "open source AI", "machine learning", "AI agent", "GPT",
         "vLLM", "Anthropic", "OpenAI"]


def main():
    out, seen = [], set()
    cand = 0
    for q in TERMS:
        enc = urllib.parse.quote(q)
        url = (f"https://api.bsky.app/xrpc/app.bsky.feed.searchPosts?q={enc}"
               "&limit=10&sort=top")
        try:
            d = json.loads(get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"}))
        except Exception as e:
            log(f"{q}: FAIL {str(e)[:50]}")
            continue
        posts = d.get("posts", [])
        log(f"{q} -> {len(posts)}")
        for p in posts:
            cand += 1
            rec = p.get("record", {}) or {}
            created = rec.get("createdAt", "")
            try:
                dt = (datetime.fromisoformat(created.replace("Z", "+00:00"))
                      if created else None)
            except Exception:
                dt = None
            if dt and dt < CUTOFF:
                continue
            likes = p.get("likeCount", 0) or 0
            reposts = p.get("repostCount", 0) or 0
            if likes < 50 and reposts < 10:
                continue
            handle = (p.get("author", {}) or {}).get("handle", "")
            uri = p.get("uri", "") or ""
            rkey = uri.rsplit("/", 1)[-1] if "/" in uri else ""
            if not handle or not rkey:
                continue
            share = f"https://bsky.app/profile/{handle}/post/{rkey}"
            if share in seen:
                continue
            seen.add(share)
            text = re.sub(r"\s+", " ", (rec.get("text", "") or "").strip())
            out.append({
                "handle": handle,
                "title": (text[:120] + "…") if len(text) > 120 else text,
                "summary": text, "text": text, "url": share, "credibility": 2,
                "published": dt.isoformat() if dt else None,
                "likeCount": likes, "repostCount": reposts,
            })
    out.sort(key=lambda x: x["likeCount"] + x["repostCount"] * 3, reverse=True)
    out = out[:8]
    atomic_write_json(out_path("bsky_items.json"), out)
    log(f"bsky_items.json: {len(out)} of {cand} candidates")


if __name__ == "__main__":
    main()
