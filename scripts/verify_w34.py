#!/usr/bin/env python3
"""Confirm the ledger catches the exact W34 defects, and would NOT have
caught the genuinely fresh items (a gate that flags everything is useless)."""
import glob, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from weekly_ledger import build_url_ledger, classify, normalize_url, load_prior_weeks, continuity_for

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ledger = build_url_ledger(sorted(glob.glob(os.path.join(repo, "digests", "*.md"))))
START, END = "2026-08-14", "2026-08-20"

CASES = [
    ("Opus 5",            "https://www.anthropic.com/news/claude-opus-5",                                    "stale"),
    ("Series E $61.5bn",  "https://www.anthropic.com/news/anthropic-raises-series-e-at-usd61-5b-post-money-valuation", "stale"),
    ("Blackstone/H&F",    "https://www.anthropic.com/news/enterprise-ai-services-company",                   "stale"),
    ("SynthID watermark", "https://www.theverge.com/ai-artificial-intelligence/980869/anthropic-claude-watermarks-synthid-text-system", "fresh"),
    ("$65bn revenue",     "https://www.bloomberg.com/news/videos/2026-08-18/anthropic-s-annualized-revenue-tops-65-billion-video",      "fresh"),
]

print(f"{'CASE':20s} {'CLASS':9s} {'FIRST SEEN':12s} {'EXPECT':7s} VERDICT")
print("-" * 66)
fails = 0
for name, url, expect in CASES:
    cls, ev = classify([url], START, END, ledger)
    is_stale_verdict = cls in ("reprint", "hum")
    ok = (expect == "stale") == is_stale_verdict
    if not ok:
        fails += 1
    print(f"{name:20s} {cls:9s} {str(ev['first_seen']):12s} {expect:7s} {'PASS' if ok else 'FAIL'}")

print()
priors = load_prior_weeks(os.path.join(repo, "weekly"), "2026-W34", limit=4)
print(f"prior roundups loaded: {[p.slug for p in priors]}")
for name, url, _ in CASES:
    hits = continuity_for([url], priors)
    if hits:
        print(f"  continuity: {name} -> already covered in {[h['slug'] for h in hits]}")

print()
print("RESULT:", "ALL PASS" if fails == 0 else f"{fails} FAILURE(S)")
sys.exit(1 if fails else 0)
