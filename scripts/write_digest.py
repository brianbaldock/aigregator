#!/usr/bin/env python3
"""
write_digest.py — deterministic markdown renderer for the AIgregator daily digest.

Reads:
    /tmp/aig/digest_items.json   (output of merge_score.py + translate.py)
    /tmp/aig/curation.json       (output of curate.py)
    ~/projects/AIgregator/digests/*.md  (prior digests, for 7-day sparkline)

Writes:
    ~/projects/AIgregator/digests/YYYY-MM-DD.md

No network. No LLM. Pure transformation of the two JSON files into the
canonical digest markdown structure.

Usage:
    python scripts/write_digest.py
    python scripts/write_digest.py --date 2026-06-08 --items /tmp/aig/digest_items.json
"""
from __future__ import annotations
import argparse, json, os, re, sys, glob
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

# Per-section limits — controls how many items appear in each block of the digest
SECTION_LIMITS = {
    "models": 5,
    "research": 5,
    "safety": 7,
    "projects": 5,
    "funding": 7,
    "tools": 5,
    "opensource": 4,
}

SECTION_HEADERS = {
    "models":     "## 🧠 Models & Releases",
    "research":   "## 🔬 Research",
    "safety":     "## 🛡️ Responsible AI, Safety & Policy",
    "projects":   "## 🎨 Cool Projects & Novel Applications",
    "funding":    "## 💰 Industry & Funding",
    "tools":      "## 🛠️ Tools & Demos",
    "opensource": "## 🌱 Open Source & Emerging",
}

SECTION_ORDER = ["models", "research", "safety", "projects", "funding", "tools", "opensource"]


def sentiment_dot(value: float) -> str:
    """Map a credibility-weighted mean sentiment to colored dot."""
    if value >= 0.2: return "🟢"
    if value <= -0.2: return "🔴"
    return "🟡"


def signed(value: float) -> str:
    """Format a number with a leading +/- and one decimal, with a +0.0 floor."""
    if -0.05 <= value <= 0.05:
        return "+0.0"
    return f"{value:+.1f}"


def sparkline_char(v: float) -> str:
    if v <= -0.7: return "▁"
    if v <= -0.5: return "▂"
    if v <= -0.3: return "▃"
    if v <= -0.1: return "▄"
    if v <= 0.1:  return "▅"
    if v <= 0.3:  return "▆"
    if v <= 0.5:  return "▇"
    return "█"


def read_prior_sentiments(digests_dir: Path, exclude_date: str, lookback: int = 7) -> list[float]:
    """Parse prior digests' dashboard lines for '+0.X sentiment' values.
    Returns at most `lookback` values, oldest first."""
    pattern = re.compile(r"([+-]?\d+\.\d+)\s*sentiment", re.I)
    paths = sorted(p for p in digests_dir.glob("*.md")
                   if re.match(r"\d{4}-\d{2}-\d{2}\.md", p.name)
                   and p.stem != exclude_date)
    paths = paths[-lookback:]
    out = []
    for p in paths:
        try:
            text = p.read_text()
            m = pattern.search(text)
            if m:
                out.append(float(m.group(1)))
        except Exception:
            pass
    return out


def domain_short(url: str) -> str:
    """For citation labels: friendly source name from a URL."""
    m = re.match(r"https?://([^/]+)", url or "")
    if not m: return url
    host = m.group(1).lower()
    if host.startswith("www."): host = host[4:]
    short_map = {
        "reuters.com": "Reuters",
        "apnews.com": "AP",
        "bloomberg.com": "Bloomberg",
        "wsj.com": "WSJ",
        "ft.com": "FT",
        "nytimes.com": "NYT",
        "theverge.com": "The Verge",
        "techcrunch.com": "TechCrunch",
        "arstechnica.com": "Ars",
        "theguardian.com": "Guardian",
        "bbc.com": "BBC",
        "bbc.co.uk": "BBC",
        "thehackernews.com": "The Hacker News",
        "axios.com": "Axios",
        "wired.com": "Wired",
        "engadget.com": "Engadget",
        "venturebeat.com": "VentureBeat",
        "openai.com": "OpenAI",
        "anthropic.com": "Anthropic",
        "deepmind.google": "DeepMind",
        "blog.google": "Google",
        "huggingface.co": "HuggingFace",
        "news.crunchbase.com": "Crunchbase",
    }
    if host in short_map: return short_map[host]
    # arxiv
    if "arxiv.org" in host:
        return "arXiv"
    # bsky/reddit
    if host == "bsky.app":
        m2 = re.search(r"/profile/([^/]+)/post/", url)
        return f"@{m2.group(1).replace('.bsky.social','')}" if m2 else "Bluesky"
    if host == "reddit.com":
        m2 = re.search(r"/r/([^/]+)", url)
        return f"r/{m2.group(1)}" if m2 else "Reddit"
    # github
    if host == "github.com":
        m2 = re.search(r"github\.com/([^/]+/[^/]+?)(?:/issues/|/pull/)(\d+)", url)
        if m2: return f"GitHub {m2.group(1)}#{m2.group(2)}"
        m2 = re.search(r"github\.com/([^/]+/[^/]+)", url)
        return f"GitHub {m2.group(1)}" if m2 else "GitHub"
    # fallback: domain bare
    return host


def arxiv_label(url: str) -> str:
    m = re.search(r"arxiv\.org/abs/([\d\.]+)v?\d*$", url)
    if m: return f"arXiv {m.group(1)}"
    return "arXiv"


def render_citations(item: dict) -> str:
    """Build the (link, link, link) citations from an item's cluster.
    Uses item['sources'] / source_domains to gather URLs in the cluster, but we
    only have the canonical URL in the JSON, so cite the canonical URL labelled
    by the source list."""
    urls = [item["url"]]
    labels = []
    # Canonical source first
    labels.append((urls[0], domain_short(urls[0])))
    return ", ".join(f"[{lbl}]({url})" for url, lbl in labels)


# Stop-words we never want capitalized as the leading word of a recovered title.
_SLUG_STOPS = {"a","an","the","of","in","on","at","to","for","and","or","but","by",
               "is","as","with","from","over","under","into","via","up","down"}

def recover_title_from_slug(url: str, original: str) -> str:
    """If the original title looks truncated, try to reconstruct from the URL slug.

    Detection: ends in '…', is shorter than 4 words after cleanup, or contains
    an unmatched truncation marker.
    Recovery: take last path segment, strip trailing IDs/numbers + file ext,
    split on '-' or '_', title-case (preserving stop-word casing for non-leading).
    Returns the longer of (original, recovered) when recovered looks reasonable;
    otherwise returns original unchanged.
    """
    if not url:
        return original
    cleaned = re.sub(r"\s*[.…]+\s*$", "", original or "").strip()
    looks_truncated = (
        (original or "").rstrip().endswith("…")
        or len(cleaned.split()) < 4
    )
    if not looks_truncated:
        return original
    # Pull last meaningful slug segment from the URL path
    try:
        from urllib.parse import urlparse
        path = urlparse(url).path.rstrip("/")
    except Exception:
        return original
    if not path:
        return original
    segments = [s for s in path.split("/") if s]
    if not segments:
        return original
    slug = segments[-1]
    # Drop trailing extensions and pure-numeric/hash IDs from common URL shapes
    slug = re.sub(r"\.(html?|php|aspx?)$", "", slug, flags=re.I)
    slug = re.sub(r"-\d{4}-\d{1,2}-\d{1,2}$", "", slug)   # trailing date stamp YYYY-MM-DD
    slug = re.sub(r"-\d{4,}$", "", slug)            # trailing -123456 ID
    slug = re.sub(r"-[a-f0-9]{8,}$", "", slug)      # trailing -deadbeef hash
    # If the trimmed slug is itself numeric or too short, give up
    if not slug or slug.isdigit() or len(slug) < 8:
        return original
    parts = re.split(r"[-_]+", slug)
    parts = [p for p in parts if p]
    if len(parts) < 3:
        return original
    # Acronym overrides — words to keep in canonical casing
    _ACRO = {"ai":"AI","agi":"AGI","gpu":"GPU","tpu":"TPU","cpu":"CPU","llm":"LLM",
             "gpt":"GPT","ipo":"IPO","api":"API","sdk":"SDK","cli":"CLI","sql":"SQL",
             "ios":"iOS","mac":"Mac","usb":"USB","aws":"AWS","gcp":"GCP","ml":"ML",
             "openai":"OpenAI","deepmind":"DeepMind","huggingface":"HuggingFace",
             "github":"GitHub","youtube":"YouTube","linkedin":"LinkedIn",
             "tiktok":"TikTok","facebook":"Facebook","whatsapp":"WhatsApp",
             "nvidia":"NVIDIA","ibm":"IBM","apl":"APL","tldr":"TLDR"}
    def cap(w: str, first: bool) -> str:
        low = w.lower()
        if low in _ACRO:
            return _ACRO[low]
        if w.isupper() and len(w) <= 5:
            return w  # keep acronyms (AI, GPU, GPT)
        if not first and low in _SLUG_STOPS:
            return low
        return w[:1].upper() + w[1:].lower()
    recovered = " ".join(cap(p, i == 0) for i, p in enumerate(parts))
    # Keep the longer plausible string
    if len(recovered.split()) > len(cleaned.split()):
        return recovered
    return original


def render_news_item(it: dict, overlay: dict, *, in_tldr: bool = False) -> str:
    """Render a news-tier line. Format:
    - SCORE FLAGSEMOJI SDOT ▤×N 🏷️ themes **Title.** Summary. Sources: [a](url), ...
    or, for TL;DR:
    SCORE FLAGSEMOJI SDOT **Title.** Summary. ([a](url), [b](url))
    """
    flag_emoji = ""
    if "cross_source" in (it.get("flags") or []): flag_emoji += "🔥"
    if it.get("section") == "safety" or "safety" in (overlay.get("themes") or []) or overlay.get("section") == "safety":
        # Mark safety items with shield in body
        pass
    # Optional shield emoji for safety-tagged
    sec = overlay.get("section", "")
    if sec == "safety": flag_emoji += "🛡️"
    if sec == "opensource" or "opensource" in (overlay.get("themes") or []): flag_emoji += "🌱"
    if sec == "projects": flag_emoji += "🎨"

    dot = sentiment_dot(it.get("sentiment", 0))
    if it.get("sentiment", 0) == 0: dot = "🟡"

    title = overlay.get("title") or it["title"]
    # If title looks truncated, try slug-recovery from the URL
    title = recover_title_from_slug(it.get("url", ""), title)
    # Strip trailing site name ONLY when it follows " - " or " | " from a known wire/news source.
    # Be conservative: must match start of separator + EOL.
    title = re.sub(
        r"\s*[|–]\s*(Reuters|AP News|Bloomberg(?:\.com)? Technology|Bloomberg Technology|Bloomberg(?:\.com)?|"
        r"WSJ|FT(?: Technology)?|Guardian|BBC(?: Technology)?|The Verge|TechCrunch|Ars Technica|AP)\s*$",
        "", title
    )
    # Also strip trailing " - SiteName" but ONLY if the site name doesn't look like content (no spaces in match)
    title = re.sub(
        r"\s+-\s+(Reuters|AP News|Bloomberg\.com|Bloomberg|WSJ|FT|Guardian|BBC|The Verge|TechCrunch|Ars Technica|AP)\s*$",
        "", title
    )
    title = title.replace("—", " - ").strip()
    # Strip trailing ellipsis variants and any leftover punctuation
    title = re.sub(r"\s*[.…]+\s*$", "", title)
    title = title.rstrip(".")
    summary = (overlay.get("summary") or it.get("summary") or "").replace("—", " - ").strip()
    if summary and not summary.endswith("."): summary += "."

    themes = overlay.get("themes") or []
    theme_str = f"🏷️ {', '.join(themes)} " if themes else ""

    sc = it.get("source_count", 1)
    src_tag = f"▤×{sc} " if sc > 1 else ""

    score = it.get("score", 0)

    # Citations: use the cluster source URLs
    # We don't have all cluster URLs in the JSON, so we use canonical + sources list
    sources_list = it.get("sources", [it.get("source", "")])
    domains = it.get("source_domains", [])
    # Build labels: prefer the actual URL, but we only have canonical. Show all source labels mapped to canonical URL.
    if in_tldr:
        # TL;DR: parenthesized citation list
        cit = render_tldr_citations(it)
        line = f"{score} {flag_emoji} {dot} **{title}.** {summary} {cit}"
        return re.sub(r" +", " ", line)
    body = f"- {score} {flag_emoji} {dot} {src_tag}{theme_str}**{title}.** {summary} Sources: {render_news_sources(it)}"
    return re.sub(r" +", " ", body)


def render_tldr_citations(it: dict) -> str:
    """For TL;DR — show all cluster source URLs in parens."""
    src_urls = it.get("source_urls") or [{"url": it["url"], "source": domain_short(it["url"]), "domain": ""}]
    parts = []
    for s in src_urls[:4]:  # cap at 4 to keep parens short
        url = s["url"]
        # Use friendly domain label, but trust the domain map first
        label = domain_short(url)
        parts.append(f"[{label}]({url})")
    return "(" + ", ".join(parts) + ")"


def render_news_sources(it: dict) -> str:
    """Body item sources line — cite all cluster URLs (one per distinct domain)."""
    src_urls = it.get("source_urls") or [{"url": it["url"], "source": "", "domain": ""}]
    parts = []
    for s in src_urls[:5]:  # cap at 5
        url = s["url"]
        label = domain_short(url)
        parts.append(f"[{label}]({url})")
    return ", ".join(parts)


def render_research_item(it: dict, overlay: dict) -> str:
    score = it.get("score", 0)
    dot = sentiment_dot(it.get("sentiment", 0))
    if it.get("sentiment", 0) == 0: dot = "🟡"
    title = overlay.get("title") or it["title"]
    title = title.replace("—", " - ").strip()
    # Strip trailing ellipsis variants and any leftover punctuation
    title = re.sub(r"\s*[.…]+\s*$", "", title)
    title = title.rstrip(".")
    summary = (overlay.get("summary") or it.get("summary") or "").replace("—", " - ").strip()
    if summary and not summary.endswith("."): summary += "."
    themes = overlay.get("themes") or []
    theme_str = f"🏷️ {', '.join(themes)} " if themes else ""
    label = arxiv_label(it["url"])
    return f"- {score} {dot} {theme_str}**{title}.** {summary} Sources: [{label}]({it['url']})"


def render_discourse(items_in_section: list[dict], curation_items: dict) -> str:
    """Group social items by subreddit / platform, then render.
    items_in_section: items where tier=='social'
    """
    by_group: dict[str, list[dict]] = defaultdict(list)
    for it in items_in_section:
        src = it["source"]
        if src.startswith("r/"):
            sub = src[2:]  # strip r/
            # Group major local-LLM/AI subs separately, lump others
            if sub in ("LocalLLaMA", "MachineLearning", "OpenAI", "ClaudeAI", "singularity", "ArtificialInteligence"):
                group_key = src
            else:
                group_key = "r/other"
        elif src.startswith("bsky:"):
            group_key = "Bluesky"
        elif src == "HN":
            group_key = "Hacker News"
        else:
            group_key = "Other"
        by_group[group_key].append(it)

    out = []
    # Order: r/LocalLLaMA, other reddits, Bluesky, HN, other
    order = []
    for k in ["r/LocalLLaMA", "r/MachineLearning", "r/OpenAI", "r/ClaudeAI",
              "r/singularity", "r/ArtificialInteligence", "r/other"]:
        if k in by_group: order.append(k)
    for k in ["Bluesky", "Hacker News", "Other"]:
        if k in by_group: order.append(k)

    for group_key in order:
        members = by_group[group_key]
        if not members: continue
        out.append(f"\n### {group_key}")
        for it in members[:5]:  # cap each subgroup at 5
            overlay = curation_items.get(it["url"], {})
            title = (overlay.get("title") or it["title"]).replace("—", " - ").strip()
            blurb = (overlay.get("summary") or "").replace("—", " - ").strip()
            if blurb and not blurb.endswith("."): blurb += "."
            # Bluesky labeling
            if it["source"].startswith("bsky:"):
                handle = it["source"][5:]
                link_label = f"@{handle.replace('.bsky.social', '')}"
                out.append(f"- [{link_label}]({it['url']}) {title} {blurb}".rstrip())
            elif it["source"] == "HN":
                out.append(f"- [HN]({it['url']}) {title} {blurb}".rstrip())
            elif group_key == "r/other":
                # Prefix with the actual subreddit since the header is generic
                sub = it["source"]
                out.append(f"- [{sub}]({it['url']}) {title} {blurb}".rstrip())
            else:
                out.append(f"- [{title}]({it['url']}) {blurb}".rstrip())
    return "\n".join(out)


def section_stats_line(items: list[dict]) -> str:
    """Render `_N items · DOT SIGNED sentiment_` line for a section."""
    n = len(items)
    if n == 0:
        return "_(quiet today)_"
    total_w = sum(it.get("credibility", 3) for it in items) or 1
    weighted = sum(it.get("sentiment", 0) * it.get("credibility", 3) for it in items)
    mean = weighted / total_w
    return f"_{n} item{'s' if n != 1 else ''} · {sentiment_dot(mean)} {signed(mean)} sentiment_"


def dashboard_line(news_items: list[dict], all_themes_used: list[str], top_mention: tuple[str, int],
                   cross_count: int, prior_sentiments: list[float], today_mean: float,
                   has_polymarket: bool, top_mover: dict | None = None, n_markets: int = 0) -> list[str]:
    """Render the dashboard blockquote lines (with mandatory two trailing spaces)."""
    n_stories = len(news_items)
    # Union of all distinct domains across clusters (each item carries source_domains[])
    domains = set()
    for it in news_items:
        for d in (it.get("source_domains") or [it.get("domain", "")]):
            if d: domains.add(d)
    n_sources = len(domains)
    dot = sentiment_dot(today_mean)
    top_name, top_cnt = top_mention if top_mention else ("(none)", 0)
    theme_counter = Counter(all_themes_used)
    top_themes = ", ".join(f"{t}×{c}" for t, c in theme_counter.most_common(5))

    # Market Pulse line: prefer the explicit top mover so the reader sees the
    # actual movement summary inline (e.g. "▲22.2pp · 5 AI markets tracked").
    if has_polymarket and top_mover:
        q = (top_mover.get("question") or "").replace('"', "'")[:80]
        chg = float(top_mover.get("change_24h_pp") or 0)
        arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "→")
        market_line = f'> **📈 MARKET PULSE:** Top mover: "{q}" {arrow}{abs(chg)}pp · {n_markets} AI markets tracked  '
    elif has_polymarket:
        market_line = f"> **📈 MARKET PULSE:** _(see Prediction Markets section, {n_markets} markets)_  "
    else:
        market_line = "> **📈 MARKET PULSE:** _(quiet today)_  "

    lines = [
        f"> **📊 TODAY:** {n_stories} stories · {n_sources} sources · {dot} {signed(today_mean)} sentiment · 🔥 {cross_count} cross-source · **TOP MENTION:** {top_name} ×{top_cnt}  ",
        f"> **🏷️ THEMES:** {top_themes}  " if top_themes else "> **🏷️ THEMES:** _(quiet today)_  ",
        market_line,
    ]
    # 7D sparkline (needs ≥5 priors)
    full_series = prior_sentiments + [today_mean]
    if len(prior_sentiments) >= 5:
        spark = "".join(sparkline_char(v) for v in full_series[-7:])
        lines.append(f"> **📉 7D SENTIMENT:** {spark} (oldest → today)  ")
    return lines


def extract_top_mention(items: list[dict], overlays: dict) -> tuple[str, int]:
    """Heuristic: count entity mentions in titles. Look for known org/person names."""
    blob = " ".join((overlays.get(it["url"], {}).get("title") or it.get("title", ""))
                    + " " + (overlays.get(it["url"], {}).get("summary") or it.get("summary", ""))
                    for it in items)
    # Big known entities to scan for
    candidates = [
        "OpenAI", "Anthropic", "Google", "DeepMind", "Microsoft", "Apple", "Meta",
        "Nvidia", "Tesla", "xAI", "SpaceX", "Cohere", "Mistral", "Stability",
        "Sam Altman", "Dario Amodei", "Elon Musk", "Sundar Pichai", "Satya Nadella",
        "Trump", "Biden", "Krishnan", "Yann LeCun", "Geoffrey Hinton",
        "Hugging Face", "ChatGPT", "Claude", "Gemini", "Llama", "DeepSeek", "Qwen",
        "AWS", "Amazon", "Palantir", "ASML",
    ]
    cnt = Counter()
    for c in candidates:
        # Word boundary count
        n = len(re.findall(r"\b" + re.escape(c) + r"\b", blob, re.I))
        if n > 0:
            cnt[c] = n
    if not cnt: return ("(none)", 0)
    return cnt.most_common(1)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="/tmp/aig/digest_items.json")
    ap.add_argument("--curation", default="/tmp/aig/curation.json")
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--digests-dir", default=str(Path.home() / "projects/AIgregator/digests"))
    ap.add_argument("--out", default=None,
                    help="Override output path (default: digests-dir/DATE.md)")
    args = ap.parse_args()

    items = json.load(open(args.items))
    curation = json.load(open(args.curation))
    curation_items = curation.get("items", {})

    digests_dir = Path(args.digests_dir)
    out_path = Path(args.out) if args.out else (digests_dir / f"{args.date}.md")

    # Group by section using curation overlay; fall back to tier for items
    # that the curator didn't cover (those get put in their tier's default bucket).
    by_section: dict[str, list[dict]] = defaultdict(list)
    for it in items:
        tier = it.get("tier", "news")
        overlay = curation_items.get(it["url"], {})
        sec = overlay.get("section")
        if not sec:
            # No curation overlay — bucket by tier
            if tier == "social": sec = "discourse"
            elif tier == "research": sec = "research"
            else: continue   # skip uncovered news items (likely hub-shaped)
        by_section[sec].append(it)

    # Apply per-section limits, sorted by score desc. Log drops for observability.
    for sec in list(by_section.keys()):
        by_section[sec].sort(key=lambda x: -x.get("score", 0))
        considered = len(by_section[sec])
        limit = SECTION_LIMITS.get(sec, 100)  # discourse + research keep all
        if sec in SECTION_LIMITS:
            by_section[sec] = by_section[sec][:limit]
        emitted = len(by_section[sec])
        dropped = considered - emitted
        if dropped > 0:
            # Surface the dropped titles so we can spot when caps are too tight.
            all_for_sec = sorted([i for i in items
                                  if curation_items.get(i["url"], {}).get("section") == sec],
                                 key=lambda x: -x.get("score", 0))
            cut = all_for_sec[limit:]
            cut_titles = [f"  - {it.get('score',0)} {it.get('title','')[:70]}" for it in cut[:5]]
            print(f"[write_digest] section {sec}: considered {considered}, emitted {emitted}, "
                  f"dropped {dropped} (top dropped):", file=sys.stderr)
            for line in cut_titles:
                print(line, file=sys.stderr)
        else:
            print(f"[write_digest] section {sec}: considered {considered}, emitted {emitted}",
                  file=sys.stderr)

    # News-tier items only (for dashboard math)
    news_section_items = []
    for sec in SECTION_ORDER:
        if sec == "research": continue
        news_section_items.extend(by_section.get(sec, []))

    # Dashboard math
    total_w = sum(it.get("credibility", 3) for it in news_section_items) or 1
    weighted_sum = sum(it.get("sentiment", 0) * it.get("credibility", 3) for it in news_section_items)
    today_mean = weighted_sum / total_w
    cross_count = sum(1 for it in news_section_items if "cross_source" in (it.get("flags") or []))

    # All themes used across rendered items
    all_themes_used = []
    for sec in SECTION_ORDER:
        for it in by_section.get(sec, []):
            ov = curation_items.get(it["url"], {})
            all_themes_used.extend(ov.get("themes") or [])

    top_mention = extract_top_mention(news_section_items, curation_items)

    prior_sentiments = read_prior_sentiments(digests_dir, args.date)

    # Build TL;DR (max 6 picks)
    tldr_urls = curation.get("tldr_order", [])[:6]
    tldr_items = []
    for url in tldr_urls:
        it = next((i for i in items if i["url"] == url), None)
        if it:
            tldr_items.append((it, curation_items.get(url, {})))

    # ---- Render ----
    lines = []
    lines.append(f"# {args.date} :: AI DAILY DIGEST")
    # Detect polymarket data (read once here; reused below for the section)
    poly_path = Path("/tmp/aig/polymarket.json")
    poly_items = []
    if poly_path.exists():
        try:
            poly_items = json.load(open(poly_path))
            if isinstance(poly_items, dict) and "markets" in poly_items:
                poly_items = poly_items["markets"]
        except Exception as e:
            print(f"[write_digest] polymarket.json parse error: {e}", file=sys.stderr)
            poly_items = []
    # Find top mover for the dashboard market-pulse line
    top_mover = None
    if poly_items:
        try:
            top_mover = max(poly_items, key=lambda m: abs(float(m.get("change_24h_pp") or 0)))
        except Exception:
            top_mover = None

    lines.append("")
    subtitle = curation.get("subtitle", "Today in AI.").replace("—", " - ")
    lines.append(f"_{subtitle}_")
    lines.append("")
    lines.extend(dashboard_line(news_section_items, all_themes_used, top_mention,
                                cross_count, prior_sentiments, today_mean,
                                has_polymarket=bool(poly_items),
                                top_mover=top_mover, n_markets=len(poly_items)))
    lines.append("")

    # TL;DR
    lines.append("## ⚡ TL;DR")
    for i, (it, overlay) in enumerate(tldr_items, 1):
        # TL;DR uses TL;DR-formatted line
        body = render_news_item(it, overlay, in_tldr=True)
        lines.append(f"{i}. {body}")
    lines.append("")

    # Section rendering — but only sections that ARE in SECTION_ORDER (excluding research order handling)
    for sec in SECTION_ORDER:
        sec_items = by_section.get(sec, [])
        lines.append(SECTION_HEADERS[sec])
        lines.append(section_stats_line(sec_items))
        for it in sec_items:
            overlay = curation_items.get(it["url"], {})
            if sec == "research":
                lines.append(render_research_item(it, overlay))
            else:
                lines.append(render_news_item(it, overlay))
        lines.append("")

    # Prediction Markets — read /tmp/aig/polymarket.json if present
    lines.append("## 📈 Prediction Markets")
    poly_path = Path("/tmp/aig/polymarket.json")
    poly_items = []
    if poly_path.exists():
        try:
            poly_items = json.load(open(poly_path))
            # Expected shape: list of {question, yes_pct, change_24h_pp, volume_usd, url}
            # Tolerate Polymarket Gamma API shape too: {markets: [...]} or raw [{...}]
            if isinstance(poly_items, dict) and "markets" in poly_items:
                poly_items = poly_items["markets"]
        except Exception as e:
            print(f"[write_digest] polymarket.json parse error: {e}", file=sys.stderr)
            poly_items = []
    if poly_items:
        lines.append(f"_{len(poly_items)} markets · AI/policy_")
        for m in poly_items[:5]:
            q = m.get("question") or m.get("title") or "(unknown)"
            yes = m.get("yes_pct") or m.get("yes_price_pct") or m.get("price_yes")
            chg = m.get("change_24h_pp") or m.get("delta_24h") or 0
            vol = m.get("volume_usd") or m.get("volume") or 0
            url = m.get("url") or m.get("permalink") or ""
            arrow = "▲" if chg > 0 else ("▼" if chg < 0 else "→")
            chg_abs = abs(chg) if isinstance(chg, (int, float)) else chg
            try:
                yes_str = f"{float(yes)*100:.0f}%" if yes and float(yes) < 1 else f"{yes}%"
            except Exception:
                yes_str = f"{yes}%"
            try:
                vol_n = float(vol)
                if vol_n >= 1_000_000:
                    vol_str = f"${vol_n/1_000_000:.1f}M"
                elif vol_n >= 1_000:
                    vol_str = f"${vol_n/1_000:.0f}K"
                else:
                    vol_str = f"${vol_n:.0f}"
            except Exception:
                vol_str = f"${vol}"
            lines.append(f"- **{q}** - {yes_str} Yes ({arrow}{chg_abs}pp 24h, {vol_str} vol) · [Polymarket]({url})")
    else:
        lines.append("_(quiet today)_")
    lines.append("")

    # Discourse
    lines.append("## 💬 Discourse")
    social_items = by_section.get("discourse", [])
    if social_items:
        lines.append(render_discourse(social_items, curation_items))
    else:
        lines.append("_(quiet today)_")
    lines.append("")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines))
    n_chars = out_path.stat().st_size
    print(f"[write_digest] wrote {out_path} ({n_chars} chars, {len(news_section_items)} news + {len(by_section.get('research', []))} research + {len(social_items)} social)")


if __name__ == "__main__":
    main()
