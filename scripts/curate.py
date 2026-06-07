#!/usr/bin/env python3
"""
curate.py — single LLM call that produces editorial overlay for digest_items.json.

Reads:  /tmp/aig/digest_items.json   (output of merge_score.py + translate.py)
Writes: /tmp/aig/curation.json       (consumed by write_digest.py)

Curation JSON shape:
    {
        "date": "YYYY-MM-DD",
        "subtitle": "One-sentence editorial framing of the day's stories.",
        "tldr_order": ["url1", "url2", ...],          # 6 URLs, ranked
        "tldr_blurbs": {"url": "One-line editorial.", ...},  # per URL
        "items": {
            "url": {
                "title": "Editorial title (cleaned, deduped).",
                "summary": "1-2 sentence editorial blurb.",
                "themes": ["theme1", "theme2"],
                "section": "models"|"research"|"safety"|"projects"|"funding"|"tools"|"opensource"
            }, ...
        }
    }

Reads OPENAI_API_KEY from env. Uses gpt-4o (needs reasoning for blurbs).
Idempotent via output file: re-run wipes & rewrites curation.json.

Usage:
    OPENAI_API_KEY=*** python scripts/curate.py
    OPENAI_API_KEY=*** python scripts/curate.py --in /tmp/aig/digest_items.json --out /tmp/aig/curation.json
"""
from __future__ import annotations
import argparse, json, os, sys, urllib.request, urllib.error
from datetime import datetime, timezone

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
MODEL = os.environ.get("AIGREGATOR_CURATE_MODEL", "gpt-4o")

CONTROLLED_THEMES = [
    "agents", "models", "evals", "safety", "policy", "alignment",
    "interpretability", "bias", "inference", "training", "hardware", "robotics",
    "multimodal", "voice", "video", "code", "science", "art", "funding",
    "opensource", "enterprise", "agi", "apps",
]

# News-tier section buckets. social/research items are placed by tier directly.
NEWS_SECTIONS = ["models", "safety", "projects", "funding", "tools", "opensource"]

SYSTEM_PROMPT = f"""You are the editorial brain for the AIgregator daily AI news digest. \
Brian writes this digest in a specific voice: dry, factual, technical, never \
marketing-flavored. Plain prose, no em dashes, no fake enthusiasm, no \
"unlock"/"delve"/"seamless"/"game-changing"/"revolutionize", no exclamation points, \
no hyped framing. The reader is a senior engineer who reads many of these. \
Surface what's actually new and what it means, not what marketing wants it to mean.

Given a list of pre-scored AI news items from the last 24 hours, you write:

1. ONE subtitle: 2-3 sentences in Brian's voice (each separated by a period, no commas \
joining clauses) framing the 2-3 biggest threads. Use proper names where you have them \
(e.g. "Sriram Krishnan exits the White House", not "Trump's AI adviser resigns"). \
Sound like a person, not a wire service. Plain prose only, no em dashes, max ~40 words.

2. A ranked TL;DR of EXACTLY 6 news-tier items (use exact URLs from the input). \
Pick for newsworthiness + corroboration. Wire-service corroborated stories (source_count >= 2) \
should generally rank first. Don't pick fluff or hub-page-shaped items.

3. For each TL;DR pick: a one-line editorial blurb (1 sentence, max ~30 words, factual, \
specific, no marketing words).

4. For EVERY news-tier item (tier="news"), include in output.items: cleaned title, \
1-2 sentence editorial summary, 1-3 themes from this exact vocabulary: \
{", ".join(CONTROLLED_THEMES)}, and a news section: \
{", ".join(NEWS_SECTIONS)} (models = model releases/launches/updates, \
safety = responsible AI / regulation / policy / executive orders, \
projects = cool indie / novel apps / interesting deployments, \
funding = $$ / deals / IPOs / equity / investments / data-center buildouts, \
tools = developer tools / demos / infrastructure, \
opensource = open weights / GitHub trends / HF trending).

COVERAGE RULE: Output ONE entry in items{{}} for EVERY news-tier URL in the input UNLESS its \
title is obviously a hub/landing page (e.g. just "AI - Bloomberg", "Artificial Intelligence News", \
"AI - Reuters", "Bloomberg Technology"). It is OK to be lossless - the next stage will pick the \
top N per section. Do NOT skip stories you find duplicative; the merge layer already deduped, \
near-duplicates are real different angles from different sources.

5. For social-tier items (tier="social", reddit/bsky/hn): include them in items{{}} too. \
Set themes=[], section="discourse", keep title as-is or lightly cleaned.

6. For research-tier items (tier="research", arXiv): pick 1-2 themes (usually research-relevant: \
training, alignment, interpretability, evals, multimodal, science), section="research".

HARD RULES:
- Use the EXACT urls provided as item keys. Do not invent or modify URLs.
- Themes MUST come from the controlled vocabulary above.
- Sections MUST come from the lists above ({", ".join(NEWS_SECTIONS)} for news, "discourse" for social, "research" for research).
- No em dashes anywhere. Use plain hyphens or restructure the sentence.
- No words like "delve", "unlock", "seamless", "game-changing", "revolutionize".
- Plain prose. Factual. The reader is technical.
- Skip an item ONLY if its title is hub-shaped (e.g. "AI - Bloomberg", "Artificial Intelligence News"). \
Everything else gets an items{{}} entry.

Output STRICT JSON matching this shape:
{{
  "subtitle": "...",
  "tldr_order": ["url", "url", "url", "url", "url", "url"],
  "tldr_blurbs": {{"url": "blurb", ...}},
  "items": {{
    "url": {{"title": "...", "summary": "...", "themes": ["..."], "section": "..."}},
    ...
  }}
}}
"""


def build_user_payload(items: list[dict]) -> tuple[str, int, int, int]:
    """Build the user message: compact list of items grouped by tier.
    Returns (payload_json, n_news, n_social, n_research)."""
    out = {"news": [], "social": [], "research": []}
    for it in items:
        tier = it.get("tier", "news")
        out[tier].append({
            "url": it["url"],
            "title": it.get("translated_title") or it["title"],
            "summary": (it.get("translated_summary") or it.get("summary") or "")[:300],
            "source": it["source"],
            "source_count": it.get("source_count", 1),
            "flags": it.get("flags", []),
            "credibility": it.get("credibility", 3),
            "via_kagi": it.get("via_kagi", False),
        })
    return (json.dumps(out, ensure_ascii=False, indent=2),
            len(out["news"]), len(out["social"]), len(out["research"]))


def call_openai(messages: list[dict], api_key: str, model: str = MODEL) -> dict | None:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "response_format": {"type": "json_object"},
        "max_tokens": 16000,
    }
    req = urllib.request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            d = json.load(r)
        return json.loads(d["choices"][0]["message"]["content"])
    except urllib.error.HTTPError as e:
        print(f"[curate] HTTP {e.code}: {e.read()[:400].decode('utf-8', 'replace')}", file=sys.stderr)
    except Exception as e:
        print(f"[curate] error: {e}", file=sys.stderr)
    return None


def validate(curation: dict, items: list[dict]) -> tuple[dict, list[str]]:
    """Validate + clean. Returns (cleaned_curation, warnings)."""
    warnings = []
    item_urls = {it["url"] for it in items}

    if "subtitle" not in curation or not curation["subtitle"]:
        warnings.append("missing subtitle")
        curation["subtitle"] = "Today in AI."
    if "—" in curation["subtitle"]:
        curation["subtitle"] = curation["subtitle"].replace("—", " - ")
        warnings.append("em dash in subtitle, replaced")

    curation.setdefault("tldr_order", [])
    curation.setdefault("tldr_blurbs", {})
    curation.setdefault("items", {})

    # Filter tldr_order to valid URLs only
    curation["tldr_order"] = [u for u in curation["tldr_order"] if u in item_urls][:6]
    if len(curation["tldr_order"]) < 4:
        warnings.append(f"tldr_order has only {len(curation['tldr_order'])} valid urls; will pad from top news by score")

    # Filter items to valid URLs only, sanitize themes + section
    cleaned_items = {}
    for url, meta in curation["items"].items():
        if url not in item_urls:
            warnings.append(f"unknown url in items: {url[:80]}")
            continue
        themes = [t for t in (meta.get("themes") or []) if t in CONTROLLED_THEMES][:3]
        section = meta.get("section", "")
        # Tier-driven section enforcement
        item = next(i for i in items if i["url"] == url)
        if item.get("tier") == "social":
            section = "discourse"
        elif item.get("tier") == "research":
            section = "research"
        elif section not in NEWS_SECTIONS:
            section = "models"  # default news bucket
            warnings.append(f"item missing/invalid section, defaulted to models: {url[:60]}")
        cleaned_items[url] = {
            "title": (meta.get("title") or item["title"]).replace("—", " - "),
            "summary": (meta.get("summary") or "").replace("—", " - "),
            "themes": themes,
            "section": section,
        }
    curation["items"] = cleaned_items
    return curation, warnings


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="/tmp/aig/digest_items.json")
    ap.add_argument("--out", dest="out", default="/tmp/aig/curation.json")
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    args = ap.parse_args()

    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("[curate] OPENAI_API_KEY not set", file=sys.stderr)
        sys.exit(2)

    items = json.load(open(args.inp))
    print(f"[curate] {len(items)} items in (news={sum(1 for i in items if i.get('tier')=='news')}, "
          f"research={sum(1 for i in items if i.get('tier')=='research')}, "
          f"social={sum(1 for i in items if i.get('tier')=='social')})")

    payload, n_news, n_social, n_research = build_user_payload(items)
    user_msg = (
        f"DATE: {args.date}\n\n"
        f"COUNTS: news={n_news}, social={n_social}, research={n_research}.\n"
        f"items{{}} MUST contain ~{n_news + n_social + n_research} entries (one per URL, "
        f"minus only hub-shaped non-stories like 'AI - Bloomberg').\n\n"
        f"ITEMS (grouped by tier):\n{payload}\n\nReturn the curation JSON now."
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_msg},
    ]
    print(f"[curate] calling {MODEL} (~{len(payload)} char payload)…")
    curation = call_openai(messages, key)
    if not curation:
        print("[curate] FAIL: no curation returned", file=sys.stderr)
        sys.exit(3)

    curation["date"] = args.date
    curation, warnings = validate(curation, items)
    for w in warnings:
        print(f"[curate] warn: {w}", file=sys.stderr)

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w") as f:
        json.dump(curation, f, ensure_ascii=False, indent=2)
    coverage_pct = int(100 * len(curation['items']) / max(1, n_news + n_social + n_research))
    print(f"[curate] wrote {args.out}: subtitle, {len(curation['tldr_order'])} tldr picks, "
          f"{len(curation['items'])} item overlays ({coverage_pct}% coverage)")
    if coverage_pct < 50:
        print(f"[curate] WARNING: only {coverage_pct}% of items were curated; digest will be thin", file=sys.stderr)


if __name__ == "__main__":
    main()
