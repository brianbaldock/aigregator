#!/usr/bin/env python3
"""polymarket.py — AI/policy prediction markets via Gamma public-search.
Writes polymarket.json. AI-keyword allowlist + bad-word blocklist to reject
non-AI markets. Ported from proven /tmp/aig/mypoly.py (2026-07-22).
"""
import json
import os
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import out_path, atomic_write_json, get, log  # noqa: E402

QUERIES = ["AI", "OpenAI", "Anthropic", "GPT", "Claude", "Gemini", "AGI",
           "AI regulation", "AI Act", "AI safety"]
AI_KW = ["ai", "openai", "anthropic", "gpt", "claude", "gemini", "agi", "llm",
         "model", "moonshot", "alibaba", "qwen", "deepseek", "grok", "xai",
         "coding arena", "benchmark", "artificial intelligence"]
BAD_KW = ["ceasefire", "ukraine", "russia", "election", "president",
          "super bowl", "gta"]


def main():
    seen = {}
    for q in QUERIES:
        url = ("https://gamma-api.polymarket.com/public-search?"
               + urllib.parse.urlencode(
                   {"q": q, "limit_per_type": 20, "events_status": "active"}))
        try:
            d = json.loads(get(url, timeout=25))
        except Exception as e:
            log(f"{q}: FAIL {str(e)[:60]}")
            continue
        events = d.get("events", []) if isinstance(d, dict) else []
        for ev in events:
            for m in ev.get("markets", []):
                cid = m.get("conditionId") or m.get("id")
                if not cid or cid in seen:
                    continue
                try:
                    vol = float(m.get("volumeNum") or m.get("volume") or 0)
                except Exception:
                    vol = 0
                if vol < 50000:
                    continue
                prices = m.get("outcomePrices")
                if isinstance(prices, str):
                    try:
                        prices = json.loads(prices)
                    except Exception:
                        prices = None
                if not prices:
                    continue
                yes = round(float(prices[0]) * 100)
                try:
                    ch = float(m.get("oneDayPriceChange") or 0) * 100
                except Exception:
                    ch = 0
                slug = ev.get("slug", "")
                qtext = ((m.get("question") or "") + " " + ev.get("title", "")).lower()
                if not any(k in qtext for k in AI_KW):
                    continue
                if any(bad in qtext for bad in BAD_KW):
                    continue
                seen[cid] = {"question": m.get("question") or ev.get("title", ""),
                             "yes_pct": yes, "change_24h_pp": round(ch),
                             "volume_usd": int(vol),
                             "url": f"https://polymarket.com/event/{slug}"}
    items = sorted(seen.values(), key=lambda x: -abs(x["change_24h_pp"]))[:5]
    atomic_write_json(out_path("polymarket.json"), items)
    log(f"{len(items)} markets")


if __name__ == "__main__":
    main()
