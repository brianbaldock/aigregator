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

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from market_rules import market_is_current, market_issue  # noqa: E402


def main():
    seen = {}
    healthy_requests = 0
    for q in QUERIES:
        url = ("https://gamma-api.polymarket.com/public-search?"
               + urllib.parse.urlencode(
                   {"q": q, "limit_per_type": 20, "events_status": "active"}))
        try:
            d = json.loads(get(url, timeout=25))
        except Exception as e:
            log(f"{q}: FAIL {str(e)[:60]}")
            continue
        events = d.get('events') if isinstance(d, dict) else None
        if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
            log(f'{q}: invalid event response schema')
            continue
        healthy_requests += 1
        for ev in events:
            for m in ev.get("markets", []):
                if not market_is_current(m, ev):
                    continue
                cid = m.get("conditionId") or m.get("id")
                if not cid or cid in seen:
                    continue
                try:
                    vol = float(m.get('volumeNum', m.get('volume', 0)))
                    prices = m.get('outcomePrices')
                    outcomes = m.get('outcomes')
                    prices = json.loads(prices) if isinstance(prices, str) else prices
                    outcomes = json.loads(outcomes) if isinstance(outcomes, str) else outcomes
                    if not isinstance(prices, list) or not isinstance(outcomes, list) or set(outcomes) != {'Yes', 'No'} or len(prices) != 2:
                        continue
                    yes = round(float(prices[outcomes.index('Yes')]) * 100, 4)
                    ch = round(float(m['oneDayPriceChange']) * 100, 4)
                except (ValueError, TypeError, KeyError, IndexError):
                    continue
                if vol < 50000:
                    continue
                slug = ev.get("slug", "")
                qtext = ((m.get("question") or "") + " " + ev.get("title", "")).lower()
                if not any(k in qtext for k in AI_KW):
                    continue
                if any(bad in qtext for bad in BAD_KW):
                    continue
                metadata = ('closed', 'active', 'acceptingOrders', 'endDate', 'endDateIso', 'umaEndDate')
                candidate = {"question": m.get("question") or ev.get("title", ""),
                             "yes_pct": yes, "change_24h_pp": ch,
                             "volume_usd": vol, "market_id": cid,
                             "url": f"https://polymarket.com/event/{slug}",
                             "event": {key: ev[key] for key in metadata if key in ev},
                             **{key: m[key] for key in metadata if key in m}}
                if market_issue(candidate):
                    continue
                seen[cid] = candidate
    items = sorted(seen.values(), key=lambda x: -abs(x["change_24h_pp"]))[:5]
    atomic_write_json(out_path("polymarket.json"), items)
    log(f"{len(items)} markets; {healthy_requests} successful queries")
    return 0 if healthy_requests else 1


if __name__ == "__main__":
    sys.exit(main())
