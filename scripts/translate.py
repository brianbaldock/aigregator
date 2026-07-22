#!/usr/bin/env python3
"""
translate.py — flag non-English titles/summaries in digest_items.json.

This script does NOT call any LLM or external API. It scans items for non-English
content (heuristic: >25% non-ASCII alphabetic chars) and marks them with
`needs_translation: true`. The cron agent's curate step is responsible for
producing English translations inline in the curation overlay (the title field
can be rendered as "Originaltitel (English: Translation)").

This is the deterministic replacement for the old Platform-API version that
quietly called gpt-4o-mini via OPENAI_API_KEY for weeks.

Usage:
    python scripts/translate.py [--in /tmp/aig/digest_items.json]

Output: items with non-English content gain a `needs_translation: true` field.
Idempotent: items already flagged (or already carrying `translated_title`) are
left alone.
"""
from __future__ import annotations
import argparse, json, sys


def is_non_english(s: str) -> bool:
    """Heuristic: >25% non-ASCII alphabetic chars => likely non-English."""
    if not s: return False
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 5: return False
    non_ascii = sum(1 for c in letters if ord(c) > 127)
    return (non_ascii / len(letters)) > 0.25


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="path", default=None,
                    help="digest_items.json (default: current run dir)")
    args = ap.parse_args()
    if args.path is None:
        import os
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from run_dir import run_dir_default
        args.path = os.path.join(run_dir_default(), "digest_items.json")

    items = json.load(open(args.path))
    n_flagged = 0
    for it in items:
        if it.get("needs_translation") or it.get("translated_title"):
            continue
        t = it.get("title") or ""
        s = it.get("summary") or ""
        if is_non_english(t) or is_non_english(s):
            it["needs_translation"] = True
            n_flagged += 1

    with open(args.path, "w") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"[translate] flagged {n_flagged}/{len(items)} items as needs_translation "
          f"(cron agent will translate inline during curate)")


if __name__ == "__main__":
    main()
