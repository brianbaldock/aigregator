#!/usr/bin/env python3
"""Tests for the four recency layers in merge_score.py.

Run: python scripts/test_recency.py
Exits non-zero on any failure. Designed to be sabotage-provable: neutering any
one layer in merge_score.py must turn at least one of these red.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import merge_score as ms

NOW = datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc)
FAILS = []


def check(name, cond, detail=""):
    if cond:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        FAILS.append(name)


def item(source, title, url, cred=5, published=""):
    return {
        "source": source, "credibility": cred, "title": title, "url": url,
        "domain": ms.domain_of(url), "summary": title, "published": published,
        "via_kagi": True,
    }


print("Layer 1 — URL date extraction")
cases = [
    ("https://www.reuters.com/world/china/major-ai-models-glance-2026-07-08/", (2026, 7, 8)),
    ("https://www.reuters.com/technology/openai-atlas-2025-10-21/", (2025, 10, 21)),
    ("https://apnews.com/2026/08/18/some-story/", (2026, 8, 18)),
    ("https://www.bloomberg.com/news/articles/2026-08-19/chip-story", (2026, 8, 19)),
    ("https://apnews.com/hub/artificial-intelligence", None),
    ("https://www.anthropic.com/news", None),
]
for url, expect in cases:
    got = ms.url_date(url)
    got_t = (got.year, got.month, got.day) if got else None
    check(f"url_date {url[:52]}", got_t == expect, f"got {got_t} want {expect}")

check("published field beats url slug",
      ms.pub_dt(item("Reuters", "t", "https://r.com/x-2020-01-01/",
                     published="2026-08-19T00:00:00+00:00")).year == 2026)

print("\nLayer 2 — hard age gate")
stale = item("Reuters", "Major AI models at a glance",
             "https://www.reuters.com/world/china/major-ai-models-glance-2026-07-08/")
fresh = item("Reuters", "Anthropic announces model",
             "https://www.reuters.com/tech/anthropic-model-2026-08-19/")
undated = item("AP News", "Meta joins OpenAI",
               "https://apnews.com/article/meta-ai-hacking-0e806abc1234")
old_research = item("arXiv:cs.AI", "A paper", "https://arxiv.org/abs/2601.00001",
                    cred=4, published="2026-06-01T00:00:00+00:00")
fresh_research = item("arXiv:cs.AI", "New paper", "https://arxiv.org/abs/2608.00001",
                      cred=4, published="2026-08-18T00:00:00+00:00")
social_old = item("r/LocalLLaMA", "post", "https://reddit.com/r/x/1",
                  cred=2, published="2026-01-01T00:00:00+00:00")

kept, dropped = ms.apply_age_gate(
    [stale, fresh, undated, old_research, fresh_research, social_old], now=NOW)
kept_u = {k["url"] for k in kept}
check("42-day-old wire dropped", stale["url"] not in kept_u)
check("today's wire kept", fresh["url"] in kept_u)
check("undated item survives gate (layer 3 handles it)", undated["url"] in kept_u)
check("79-day-old arXiv dropped", old_research["url"] not in kept_u)
check("1-day-old arXiv kept", fresh_research["url"] in kept_u)
check("social bypasses gate (own fetcher cutoff)", social_old["url"] in kept_u)

print("\nLayer 3 — undated items are second-class")
scored = ms.cluster_and_score([undated])
u = scored[0]
check("undated single-source demoted out of top", u["section"] == "more",
      f"section={u['section']}")
check("undated flagged", "undated" in u["flags"])

dated_single = ms.cluster_and_score([fresh])[0]
check("dated cred-5 single keeps top slot", dated_single["section"] == "top")
check("dated item not flagged undated", "undated" not in dated_single["flags"])

# undated member must not corroborate a dated story
pair_dated = item("Reuters", "Anthropic pauses model rollout amid safety review",
                  "https://www.reuters.com/tech/anthropic-pauses-rollout-2026-08-19/")
pair_undated = item("Bloomberg", "Anthropic pauses model rollout amid safety review",
                    "https://www.bloomberg.com/technology-ai")
c = ms.cluster_and_score([pair_dated, pair_undated])
target = [x for x in c if "anthropic-pauses" in x["url"]]
check("undated member excluded from cluster citations",
      target and target[0]["source_count"] == 1,
      f"source_count={target[0]['source_count'] if target else 'n/a'}")
check("undated member does not create cross_source badge",
      target and "cross_source" not in target[0]["flags"])

print("\nLayer 4 — cluster date-spread guard")
a = item("Reuters", "White House releases national AI framework rules",
         "https://www.reuters.com/world/us/white-house-national-ai-framework-2026-08-19/")
b = item("AP News", "White House releases national AI framework rules",
         "https://apnews.com/2026/08/18/white-house-national-ai-framework/")
old = item("Bloomberg", "White House releases national AI framework rules",
           "https://www.bloomberg.com/news/articles/2026-03-20/white-house-national-ai-framework")

# feed the gate first, as the pipeline does, then cluster
gated, _ = ms.apply_age_gate([a, b, old], now=NOW)
res = ms.cluster_and_score(gated)
top = max(res, key=lambda x: x["source_count"])
check("two same-week wires still cluster", top["source_count"] == 2,
      f"source_count={top['source_count']}")
check("152-day-old member not cited", "bloomberg.com" not in top["source_domains"],
      f"domains={top['source_domains']}")

# direct spread test, bypassing the age gate, to prove layer 4 stands alone
res2 = ms.cluster_and_score([a, b, old])
top2 = max(res2, key=lambda x: x["source_count"])
check("date-spread guard strips off-date member even without age gate",
      "bloomberg.com" not in top2["source_domains"],
      f"domains={top2['source_domains']}")

print()
if FAILS:
    print(f"{len(FAILS)} FAILED: {FAILS}")
    sys.exit(1)
print("all recency tests passed")
