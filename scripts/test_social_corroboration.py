#!/usr/bin/env python3
"""Layer 5 tests: social posts are not corroboration for a news event.

An r/singularity thread ABOUT an openai.com announcement is a reaction to the
same single source, not a second outlet that confirmed it. It must not:
  - count toward source_count / the cross-source score bonus
  - raise the cross_source flag or the reader-visible cross-source badge
  - appear as a citation in the news sections

It MUST still survive into the output as a standalone social-tier item.

Run: .venv/bin/python scripts/test_social_corroboration.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from merge_score import cluster_and_score, SOCIAL_DOMAINS  # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"\n        {detail}" if detail and not cond else ""))


def mk(source, cred, title, url, published, summary="body text here"):
    from urllib.parse import urlparse
    host = urlparse(url).netloc
    if host.startswith("www."):
        host = host[4:]
    return {
        "source": source, "credibility": cred, "title": title, "url": url,
        "summary": summary, "domain": host, "published": published,
        "via_kagi": False, "kind": "news",
    }


def by_url(items, needle):
    return next((i for i in items if needle in i["url"]), None)


print("Layer 5: social non-corroboration")

# --- Scenario 1: vendor blog + reddit thread about it -------------------
vendor = mk("OpenAI blog", 4, "Path to Astra: critical capabilities and frontier safeguards",
            "https://openai.com/index/path-to-astra", "2026-09-02T10:00:00+00:00")
thread = mk("r/singularity", 2, "Path to Astra: critical capabilities and frontier safeguards",
            "https://www.reddit.com/r/singularity/comments/1w4o0a1/path_to_astra/",
            "2026-09-02T11:00:00+00:00")
out = cluster_and_score([vendor, thread])
v = by_url(out, "openai.com")
check("vendor item survives", v is not None)
if v:
    check("source_count is 1, not 2", v["source_count"] == 1, f"got {v['source_count']}")
    check("no cross_source flag", "cross_source" not in v["flags"], f"flags={v['flags']}")
    check("no reddit citation in source_urls",
          all(s["domain"] not in SOCIAL_DOMAINS for s in v["source_urls"]),
          f"source_urls={v['source_urls']}")
    check("no phantom +3 cross-source bonus", v["score"] == 4 * 2, f"score={v['score']}")
t = by_url(out, "reddit.com")
check("reddit post re-emitted as standalone item", t is not None)
if t:
    check("re-emitted reddit keeps its source label", t["source"] == "r/singularity", f"got {t['source']}")
    check("re-emitted reddit is single-source", t["source_count"] == 1)

# --- Scenario 2: genuine multi-outlet story keeps its badge -------------
a = mk("Reuters", 5, "Pentagon blacklisting of Anthropic was unlawful, US judge rules",
       "https://www.reuters.com/legal/pentagon-anthropic-2026-08-28/", "2026-08-28T09:00:00+00:00")
b = mk("The Guardian", 5, "Pentagon blacklisting of Anthropic was unlawful, US judge rules",
       "https://www.theguardian.com/tech/2026/aug/28/pentagon-anthropic", "2026-08-28T10:00:00+00:00")
c = mk("r/technology", 2, "Pentagon blacklisting of Anthropic was unlawful, US judge rules",
       "https://www.reddit.com/r/technology/comments/abc123/pentagon_anthropic/", "2026-08-28T11:00:00+00:00")
out2 = cluster_and_score([a, b, c])
w = by_url(out2, "reuters.com")
check("real two-outlet story still clusters", w is not None and w["source_count"] == 2,
      f"got {w['source_count'] if w else None}")
if w:
    check("real story keeps cross_source flag", "cross_source" in w["flags"], f"flags={w['flags']}")
    check("real story cites no subreddit",
          all(s["domain"] not in SOCIAL_DOMAINS for s in w["source_urls"]),
          f"source_urls={[s['domain'] for s in w['source_urls']]}")

# --- Scenario 3: two social posts about each other stay social ----------
s1 = mk("r/LocalLLaMA", 2, "Qwen3.8 Flash Next benchmarks are wild",
        "https://www.reddit.com/r/LocalLLaMA/comments/aaa/qwen/", "2026-08-27T09:00:00+00:00")
s2 = mk("bsky:someone", 2, "Qwen3.8 Flash Next benchmarks are wild",
        "https://bsky.app/profile/x/post/bbb", "2026-08-27T10:00:00+00:00")
out3 = cluster_and_score([s1, s2])
check("social-only cluster is not destroyed", len(out3) >= 1, f"got {len(out3)} items")
check("social-only cluster keeps a social canonical",
      any(i["domain"] in SOCIAL_DOMAINS for i in out3))

# --- Scenario 4 (meta): the probe can actually fail ---------------------
# If SOCIAL_DOMAINS were empty, scenario 1 would regress. Prove the assertion
# is load-bearing rather than vacuously true.
import merge_score as _ms  # noqa: E402
_saved = _ms.SOCIAL_DOMAINS
try:
    _ms.SOCIAL_DOMAINS = set()
    sab = _ms.cluster_and_score([dict(vendor), dict(thread)])
    sv = by_url(sab, "openai.com")
    check("meta: with the gate disabled the bug returns",
          sv is not None and sv["source_count"] == 2 and "cross_source" in sv["flags"],
          f"sabotaged run gave source_count={sv['source_count'] if sv else None} "
          f"flags={sv['flags'] if sv else None} — probe is not load-bearing")
finally:
    _ms.SOCIAL_DOMAINS = _saved

print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
if FAIL:
    print("FAILED: " + ", ".join(FAIL))
    sys.exit(1)
print("all social-corroboration tests passed")
