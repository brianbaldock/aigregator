#!/usr/bin/env python3
"""
curate.py — schema + validator for the AIgregator digest curation JSON.

This script does NOT call any LLM. The curation JSON is produced by the cron
agent itself (using its own model, e.g. GPT-5.5 via openai-codex or claude-cli
sonnet) via the prompt template below. curate.py provides:

  - The CURATION_PROMPT_TEMPLATE the cron embeds when asking its model to
    produce the curation.
  - validate(): cleans + validates a curation dict. Drops invalid URLs, coerces
    unknown themes/sections, enforces voice rules (no em dashes, banned words).
  - main(): CLI for validating a curation.json on disk in-place.

Usage:
    # Inside the cron agent, the agent produces /tmp/aig/curation.json directly.
    # Then the cron runs:
    python scripts/curate.py --validate --in /tmp/aig/curation.json --items /tmp/aig/digest_items.json
    # Which rewrites the file in place with cleaned/validated content, exits non-zero on hard failures.

    # To print the prompt template the cron should pass to its model:
    python scripts/curate.py --print-prompt
"""
from __future__ import annotations
import argparse, json, os, sys

CONTROLLED_THEMES = [
    "agents", "models", "evals", "safety", "policy", "alignment",
    "interpretability", "bias", "inference", "training", "hardware", "robotics",
    "multimodal", "voice", "video", "code", "science", "art", "funding",
    "opensource", "enterprise", "agi", "apps",
]

NEWS_SECTIONS = ["models", "safety", "projects", "funding", "tools", "opensource"]

BANNED_WORDS = [
    "delve", "unlock", "seamless", "game-changing", "game changing",
    "revolutionize", "revolutionise", "groundbreaking", "cutting-edge",
    "synergy", "leverage", "robust", "navigate the",
]

CURATION_PROMPT_TEMPLATE = """\
You are the editorial brain for the AIgregator daily AI news digest. Brian writes \
this digest in a specific voice: dry, factual, technical, never marketing-flavored. \
Plain prose, no em dashes, no fake enthusiasm, no exclamation points, no hyped framing. \
The reader is a senior engineer who reads many of these. Surface what's actually new \
and what it means, not what marketing wants it to mean.

You have access to {items_path} (the merged item set from merge_score.py). It is a \
JSON list. Each item has: url, title, summary, source, tier (news|social|research), \
source_count, flags, credibility, source_domains, source_urls.

Read it. Then write {out_path} with a curation JSON in this EXACT shape:

{{
  "subtitle": "2-3 sentences in Brian's voice framing the day's big threads. Use proper names. Plain prose. Max ~40 words.",
  "tldr_order": ["url1", "url2", "url3", "url4", "url5", "url6"],
  "tldr_blurbs": {{"url1": "one-line blurb", ...}},
  "items": {{
    "url1": {{"title": "cleaned title", "summary": "1-2 sentence editorial", "themes": ["theme1"], "section": "models"}},
    ...
  }}
}}

RULES:
- Voice: dry, factual, technical. NO em dashes. NO words: delve, unlock, seamless, \
game-changing, revolutionize, groundbreaking, cutting-edge, synergy, leverage. No \
exclamation points. No marketing framing.
- TLDR: EXACTLY 6 picks from tier="news", ranked by newsworthiness + corroboration. \
Wire-corroborated stories (source_count >= 2) generally rank first. Skip hub-page \
titles like "AI - Bloomberg", "Artificial Intelligence News", "Bloomberg Technology".
- ITEMS: include one entry per URL for ALL items in the input UNLESS the title is \
obviously a hub/landing page. Lossless coverage — write_digest.py will pick top N \
per section.
- THEMES (controlled vocabulary, pick 1-3 per item): {themes}
- SECTIONS for news tier: {sections}
- For social tier (reddit/bsky/hn): themes=[], section="discourse"
- For research tier (arXiv): pick 1-2 research-relevant themes, section="research"

TRANSLATION: if an item has "needs_translation": true, render its title as \
"Original Title (English: Your Translation Here)" and write the summary in \
English. This is how non-English wire stories appear in the digest.

SECTION MEANINGS:
- models: model releases, launches, updates, weights drops. NEW model from a lab.
- safety: responsible AI, regulation, policy, executive orders, governance, calls for moratoriums, AI safety research findings
- projects: cool indie work, novel apps, interesting deployments, art/games, surprising research-in-the-wild. NOT essays/op-eds about AI. If the item is primarily a developer tool, SDK, or a demo of agent/coding capability (something builders use to build), it belongs in `tools`, NOT here. Projects are end-user-facing things someone shipped (apps, art, games).
- funding: $$, deals, IPOs, equity, investments, data-center buildouts, market dynamics, M&A, infra spending
- tools: developer tools, libraries, SDKs, frameworks, API launches, IDE plugins, eval/benchmark harnesses, agentic-coding-in-production writeups, and concrete demos of developer or agent capabilities. This is where "someone built X with Codex/Claude/an agent", "new library/SDK/CLI", and capability demos go. Don't pad it with vendor marketing fluff, but DO populate it whenever a genuine builder-facing tool or capability demo appears in the input. On a normal AI news day there is almost always at least one.
- opensource: open weights releases, GitHub trending, HuggingFace trending, open-model benchmarks
- (research and discourse handled automatically by tier)

OPINION/ANALYSIS pieces (e.g. "AI Promised a Revolution and Companies Are Still Waiting", "Hospitals Are a Proving Ground for AI", "Why Many Americans Turn to AI for Health") are NOT projects. Put them in models if they're about model capabilities/limitations, in safety if they're about governance/risk, or in funding if they're about industry/business reality. Projects should be specific things someone built.

USE THE EXACT URLs from the input as keys. Do not invent, modify, or reformat URLs.

After you write the file, run:
  cd ~/projects/AIgregator && source .venv/bin/activate && \\
  python scripts/curate.py --validate --in {out_path} --items {items_path}

If validate prints "OK", proceed to write_digest.py. If it prints "FAIL", fix the \
issues it lists and re-validate."""


def print_prompt(items_path: str = "/tmp/aig/digest_items.json",
                 out_path: str = "/tmp/aig/curation.json") -> str:
    return CURATION_PROMPT_TEMPLATE.format(
        items_path=items_path,
        out_path=out_path,
        themes=", ".join(CONTROLLED_THEMES),
        sections=", ".join(NEWS_SECTIONS),
    )


def _strip_voice_violations(text: str) -> tuple[str, list[str]]:
    """Strip em dashes and banned words. Returns (cleaned_text, warnings)."""
    warnings = []
    cleaned = text
    if "—" in cleaned:
        cleaned = cleaned.replace("—", " - ")
        warnings.append("em dash replaced with hyphen")
    if "–" in cleaned:  # en-dash too
        cleaned = cleaned.replace("–", "-")
        warnings.append("en dash replaced with hyphen")
    lower = cleaned.lower()
    for word in BANNED_WORDS:
        if word in lower:
            warnings.append(f"banned word '{word}' detected (not auto-stripped)")
    return cleaned, warnings


def validate(curation: dict, items: list[dict]) -> tuple[dict, list[str], list[str]]:
    """Validate + clean curation against the item set.
    Returns (cleaned_curation, warnings, hard_errors).
    If hard_errors is non-empty, the curation is not safe to use.
    """
    warnings: list[str] = []
    hard_errors: list[str] = []
    item_urls = {it["url"] for it in items}
    item_by_url = {it["url"]: it for it in items}

    # Subtitle
    sub = curation.get("subtitle") or ""
    if not sub.strip():
        hard_errors.append("missing or empty subtitle")
        sub = "Today in AI."
    sub, sub_warn = _strip_voice_violations(sub)
    warnings.extend(f"subtitle: {w}" for w in sub_warn)
    if len(sub.split()) > 60:
        warnings.append(f"subtitle is long ({len(sub.split())} words; prefer <40)")
    curation["subtitle"] = sub.strip()

    # TLDR order — must be exactly 6 valid URLs
    raw_tldr = curation.get("tldr_order") or []
    valid_tldr = [u for u in raw_tldr if u in item_urls and item_by_url[u].get("tier") == "news"]
    seen = set()
    valid_tldr = [u for u in valid_tldr if not (u in seen or seen.add(u))]  # dedup
    if len(valid_tldr) < 4:
        hard_errors.append(f"tldr_order has only {len(valid_tldr)} valid news-tier URLs; need at least 4")
    elif len(valid_tldr) < 6:
        warnings.append(f"tldr_order has {len(valid_tldr)} valid URLs; padding from top news by score")
        news_items = sorted([i for i in items if i.get("tier") == "news"],
                            key=lambda x: -x.get("score", 0))
        for it in news_items:
            if it["url"] in valid_tldr: continue
            valid_tldr.append(it["url"])
            if len(valid_tldr) >= 6: break
    curation["tldr_order"] = valid_tldr[:6]

    # TLDR blurbs — must be present for each tldr URL
    raw_blurbs = curation.get("tldr_blurbs") or {}
    cleaned_blurbs = {}
    for url in curation["tldr_order"]:
        b = raw_blurbs.get(url) or ""
        if not b.strip():
            warnings.append(f"missing tldr blurb for {url[:60]}; using item summary")
            b = item_by_url[url].get("summary", "")
        b, w = _strip_voice_violations(b)
        for ww in w: warnings.append(f"tldr blurb: {ww}")
        cleaned_blurbs[url] = b.strip()
    curation["tldr_blurbs"] = cleaned_blurbs

    # Items — coerce sections by tier, validate themes
    raw_items = curation.get("items") or {}
    cleaned_items = {}
    for url, meta in raw_items.items():
        if url not in item_urls:
            warnings.append(f"unknown URL in items, dropped: {url[:80]}")
            continue
        item = item_by_url[url]
        tier = item.get("tier", "news")
        themes = [t for t in (meta.get("themes") or []) if t in CONTROLLED_THEMES][:3]
        section = (meta.get("section") or "").strip().lower()
        # Tier-driven section coercion
        if tier == "social":
            section = "discourse"
        elif tier == "research":
            section = "research"
        elif section not in NEWS_SECTIONS:
            warnings.append(f"invalid/missing section for {url[:60]}, defaulting to projects")
            section = "projects"
        title, tw = _strip_voice_violations(meta.get("title") or item["title"])
        summary, sw = _strip_voice_violations(meta.get("summary") or item.get("summary", ""))
        for w in tw + sw: warnings.append(f"item {url[:40]}: {w}")
        cleaned_items[url] = {
            "title": title.strip(),
            "summary": summary.strip(),
            "themes": themes,
            "section": section,
        }
    curation["items"] = cleaned_items

    # Coverage check (warn-only — write_digest can still render uncovered items
    # by falling back to raw item title/summary)
    coverage = len(cleaned_items) / max(1, len(items)) * 100
    if coverage < 50:
        warnings.append(f"only {coverage:.0f}% of items have curation overlays; digest will be thin")

    # Translation check — items flagged needs_translation should have an
    # English-looking title in the curation overlay
    untranslated = []
    for it in items:
        if not it.get("needs_translation"): continue
        url = it["url"]
        overlay = cleaned_items.get(url)
        if not overlay: continue
        title = overlay.get("title") or ""
        # Title still looks non-English if >25% non-ASCII alpha
        letters = [c for c in title if c.isalpha()]
        if letters:
            non_ascii = sum(1 for c in letters if ord(c) > 127)
            if non_ascii / len(letters) > 0.25 and "English:" not in title:
                untranslated.append(url[:60])
    if untranslated:
        warnings.append(f"{len(untranslated)} items flagged needs_translation lack English in title: {untranslated[:3]}")

    return curation, warnings, hard_errors


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true",
                    help="Validate + clean curation.json in place")
    ap.add_argument("--print-prompt", action="store_true",
                    help="Print the curation prompt template for the cron agent")
    ap.add_argument("--in", dest="path", default="/tmp/aig/curation.json")
    ap.add_argument("--items", default="/tmp/aig/digest_items.json")
    args = ap.parse_args()

    if args.print_prompt:
        print(print_prompt(args.items, args.path))
        return

    if not args.validate:
        ap.print_help()
        sys.exit(1)

    if not os.path.exists(args.path):
        print(f"[curate] FAIL: curation file not found: {args.path}", file=sys.stderr)
        sys.exit(2)
    if not os.path.exists(args.items):
        print(f"[curate] FAIL: items file not found: {args.items}", file=sys.stderr)
        sys.exit(2)

    try:
        curation = json.load(open(args.path))
    except json.JSONDecodeError as e:
        print(f"[curate] FAIL: curation file is not valid JSON: {e}", file=sys.stderr)
        sys.exit(2)
    items = json.load(open(args.items))

    cleaned, warnings, errors = validate(curation, items)

    for w in warnings:
        print(f"[curate] warn: {w}", file=sys.stderr)
    for e in errors:
        print(f"[curate] ERROR: {e}", file=sys.stderr)

    if errors:
        print(f"[curate] FAIL: {len(errors)} hard error(s); not safe to render", file=sys.stderr)
        sys.exit(3)

    # Write back cleaned version
    with open(args.path, "w") as f:
        json.dump(cleaned, f, ensure_ascii=False, indent=2)
    coverage_pct = int(100 * len(cleaned["items"]) / max(1, len(items)))
    print(f"[curate] OK: subtitle ok, {len(cleaned['tldr_order'])} tldr picks, "
          f"{len(cleaned['items'])} item overlays ({coverage_pct}% coverage)")


if __name__ == "__main__":
    main()
