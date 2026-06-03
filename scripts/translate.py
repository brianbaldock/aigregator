#!/usr/bin/env python3
"""
translate.py — detect non-English titles/summaries in digest_items.json and
translate them inline. Renders as "Original (English: ...)".

Reads OPENAI_API_KEY from env. Uses gpt-4o-mini (cheap). Skips items already
ASCII-dominant. Idempotent: items already carrying 'translated_title' are
left alone.

Usage:
    OPENAI_API_KEY=sk-... python scripts/translate.py [--in /tmp/aig/digest_items.json]
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.request, urllib.error

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = "gpt-4o-mini"

def is_non_english(s: str) -> bool:
    """Heuristic: >25% non-ASCII alphabetic chars → likely non-English."""
    if not s: return False
    letters = [c for c in s if c.isalpha()]
    if len(letters) < 5: return False
    non_ascii = sum(1 for c in letters if ord(c) > 127)
    return (non_ascii / len(letters)) > 0.25

def translate(text: str, api_key: str) -> str | None:
    payload = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": "Translate the user's text to natural English. Output ONLY the translation, no quotes, no preface, no explanation."},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": 400,
    }
    req = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            d = json.load(r)
        return d["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        print(f"[translate] HTTP {e.code}: {e.read()[:200].decode('utf-8', 'replace')}", file=sys.stderr)
    except Exception as e:
        print(f"[translate] error: {e}", file=sys.stderr)
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="path", default="/tmp/aig/digest_items.json")
    args = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("[translate] OPENAI_API_KEY not set; skipping translation", file=sys.stderr)
        sys.exit(0)

    items = json.load(open(args.path))
    n_done = n_fail = 0
    for it in items:
        if it.get("translated_title") or it.get("translated_summary"):
            continue
        t = it.get("title") or ""
        s = it.get("summary") or ""
        need = is_non_english(t) or is_non_english(s)
        if not need: continue
        if is_non_english(t):
            tr = translate(t, key)
            if tr:
                it["translated_title"] = tr
                n_done += 1
            else:
                n_fail += 1
        if is_non_english(s):
            tr = translate(s[:600], key)
            if tr:
                it["translated_summary"] = tr
                n_done += 1
            else:
                n_fail += 1

    with open(args.path, "w") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    print(f"[translate] translated {n_done} fields, {n_fail} failed across {len(items)} items")

if __name__ == "__main__":
    main()
