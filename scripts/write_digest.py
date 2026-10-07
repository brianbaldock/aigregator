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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from market_rules import filter_markets

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


def read_prior_sentiments(digests_dir: Path, exclude_date: str, lookback: int = 6) -> list[float]:
    """Parse prior digests' dashboard lines for '+0.X sentiment' values.
    Returns at most `lookback` values, oldest first."""
    pattern = re.compile(r"([+-]?\d+\.\d+)\s*sentiment", re.I)
    earliest = (datetime.fromisoformat(exclude_date) - timedelta(days=lookback)).date().isoformat()
    paths = sorted(p for p in digests_dir.glob("*.md")
                   if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.md", p.name)
                   and earliest <= p.stem < exclude_date)
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
    sec = overlay.get("section", "") or it.get("section", "")
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
    if it.get("discovery_url"):
        body += f" · Discovered via [{it['discovery_source']}]({it['discovery_url']})"
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
    for s in src_urls:  # every counted source remains inspectable in the body
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
    return f"- {score} {dot} {theme_str}**{title}.** {summary} Sources: {render_news_sources(it)}"


def social_group(item):
    source = item["source"]
    if source.startswith("r/"):
        major = {"LocalLLaMA", "MachineLearning", "OpenAI", "ClaudeAI", "singularity", "ArtificialInteligence"}
        return source if source[2:] in major else "r/other"
    if source.startswith("bsky:"):
        return "Bluesky"
    return "Hacker News" if source == "HN" else "Other"


def render_discourse(items_in_section: list[dict], curation_items: dict) -> str:
    """Group social items by subreddit / platform, then render.
    items_in_section: items where tier=='social'
    """
    by_group: dict[str, list[dict]] = defaultdict(list)
    for it in items_in_section:
        group_key = social_group(it)
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
        for it in members:  # caps already applied to the final selection
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
    if len(prior_sentiments) == 6:
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


def select_items(items, curation):
    """Choose the body once; TLDR picks reserve slots rather than vanishing."""
    by_section = defaultdict(list)
    excluded = curation.get("exclusions", {})
    for item in items:
        if item["url"] in excluded:
            continue
        section = curation["items"][item["url"]]["section"]
        by_section[section].append(item)
    tldr = set(curation["tldr_order"])
    for section, pool in by_section.items():
        ranked = sorted(pool, key=lambda item: -item["score"])
        if section == "discourse":
            groups = Counter()
            kept = []
            for item in ranked:
                group = social_group(item)
                if groups[group] < 5:
                    kept.append(item)
                    groups[group] += 1
            by_section[section] = kept
            continue
        reserved = [item for item in ranked if item["url"] in tldr]
        limit = max(SECTION_LIMITS.get(section, len(ranked)), len(reserved))
        rest = [item for item in ranked if item["url"] not in tldr]
        keep = {item["url"] for item in reserved + rest[:limit - len(reserved)]}
        by_section[section] = [item for item in ranked if item["url"] in keep]
    return dict(by_section)


def render_market_section(markets, has_omissions=False):
    lines = []
    if has_omissions:
        lines.append('_Market data unavailable or invalid/expired records omitted; counts cover displayed markets only._')
    if not markets:
        return lines + ['_(quiet today)_']
    lines.append(f'_{len(markets)} markets · AI/policy_')
    for market in markets:
        delta, volume = market['change_24h_pp'], market['volume_usd']
        arrow = '▲' if delta > 0 else '▼' if delta < 0 else '→'
        volume_text = (f'${volume/1_000_000:.1f}M' if volume >= 1_000_000
                       else f'${volume/1_000:.0f}K' if volume >= 1_000 else f'${volume:.0f}')
        lines.append(f"- **{market['question']}** - {market['yes_pct']:g}% Yes "
                     f"({arrow}{abs(delta)}pp 24h, {volume_text} vol) · [Polymarket]({market['url']})")
    return lines


def source_health_note(manifest):
    if manifest is None:
        return ''
    if not isinstance(manifest, dict):
        raise ValueError('source manifest must be an object')
    labels = {'arxiv': 'arXiv', 'bsky': 'Bluesky', 'hn': 'Hacker News', 'kagi': 'Kagi',
              'opensource': 'Open-source feeds', 'polymarket': 'Polymarket', 'reddit': 'Reddit', 'rss': 'RSS'}
    failed = []
    for name, entry in sorted(manifest.items()):
        if (name not in labels or not isinstance(entry, dict)
                or entry.get('status') not in {'OK', 'EMPTY', 'FAIL', 'TIMEOUT', 'GLOBAL_DEADLINE'}):
            raise ValueError('invalid source status in manifest')
        if entry['status'] not in {'OK', 'EMPTY'}:
            failed.append(labels[name])
    return f"_Collection gaps: {', '.join(failed)} unavailable; these sources are omitted._" if failed else ''


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default=None,
                    help="digest_items.json (default: current run dir)")
    ap.add_argument("--curation", default=None,
                    help="curation.json (default: current run dir)")
    ap.add_argument("--date", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--digests-dir", default=str(Path.home() / "projects/AIgregator/digests"))
    ap.add_argument("--out", default=None,
                    help="Override output path (default: digests-dir/DATE.md)")
    ap.add_argument("--polymarket", default=None,
                    help="polymarket.json path (default: alongside --items)")
    args = ap.parse_args()

    if args.items is None or args.curation is None:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from run_dir import run_dir_default
        rd = run_dir_default()
        if args.items is None:
            args.items = os.path.join(rd, "digest_items.json")
        if args.curation is None:
            args.curation = os.path.join(rd, "curation.json")

    with open(args.items, encoding='utf-8') as source:
        items = json.load(source)
    with open(args.curation, encoding='utf-8') as source:
        curation = json.load(source)
    manifest_path = Path(args.items).parent / 'gather_manifest.json'
    source_manifest = None
    if manifest_path.exists():
        with manifest_path.open(encoding='utf-8') as source:
            source_manifest = json.load(source)
    coverage_note = source_health_note(source_manifest)
    from curate import validate
    curation, warnings, errors = validate(curation, items)
    for warning in warnings:
        print(f"[write_digest] warn: {warning}", file=sys.stderr)
    if errors:
        for error in errors:
            print(f"[write_digest] FAIL: {error}", file=sys.stderr)
        raise SystemExit(3)
    # polymarket.json lives in the same run dir as digest_items.json unless
    # overridden. Derive it from --items so per-run gather dirs are honored.
    poly_path = Path(args.polymarket) if args.polymarket else (
        Path(args.items).parent / "polymarket.json")
    curation_items = curation.get("items", {})

    digests_dir = Path(args.digests_dir)
    out_path = Path(args.out) if args.out else (digests_dir / f"{args.date}.md")

    by_section = select_items(items, curation)
    for section, picked in by_section.items():
        considered = sum(1 for overlay in curation_items.values() if overlay["section"] == section)
        print(f"[write_digest] section {section}: considered {considered}, emitted {len(picked)}", file=sys.stderr)

    # News-tier items only (for dashboard math)
    news_section_items = []
    for sec in SECTION_ORDER:
        news_section_items.extend(item for item in by_section.get(sec, []) if item["tier"] == "news")

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
    # Optional markets are validated ONCE before both dashboard and body.
    clock = datetime.now(timezone.utc)
    if args.date != clock.date().isoformat():
        clock = datetime.fromisoformat(args.date).replace(tzinfo=timezone.utc)
    poly_items, market_issues = [], []
    try:
        with poly_path.open() as source:
            poly_items, market_issues = filter_markets(json.load(source), clock)
    except (OSError, ValueError):
        market_issues = ["market data unavailable or malformed"]
    for issue in market_issues:
        print(f"[write_digest] omitted {issue}", file=sys.stderr)
    top_mover = max(poly_items, key=lambda m: abs(m["change_24h_pp"]), default=None)

    lines.append("")
    subtitle = curation.get("subtitle", "Today in AI.").replace("—", " - ")
    lines.append(f"_{subtitle}_")
    lines.append("")
    lines.extend(dashboard_line(news_section_items, all_themes_used, top_mention,
                                cross_count, prior_sentiments, today_mean,
                                has_polymarket=bool(poly_items),
                                top_mover=top_mover, n_markets=len(poly_items)))
    if coverage_note:
        lines.append(coverage_note)
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

    # Render only the normalized, retained market selection.
    lines.append("## 📈 Prediction Markets")
    lines.extend(render_market_section(poly_items, bool(market_issues)))
    lines.append("")

    # Discourse
    lines.append("## 💬 Discourse")
    social_items = by_section.get("discourse", [])
    if social_items:
        lines.append(render_discourse(social_items, curation_items))
    else:
        lines.append("_(quiet today)_")
    lines.append("")

    markdown = "\n".join(lines)
    from validate_digest import validate_artifact
    report = validate_artifact(items, curation, poly_items, markdown, args.date, now=clock,
                               prior_sentiments=prior_sentiments, source_manifest=source_manifest, market_issues=market_issues)
    if report["errors"]:
        for error in report["errors"]:
            print(f"[write_digest] FAIL: {error}", file=sys.stderr)
        raise SystemExit(4)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(markdown)
    n_chars = out_path.stat().st_size
    print(f"[write_digest] wrote {out_path} ({n_chars} chars, {len(news_section_items)} news + {len(by_section.get('research', []))} research + {len(social_items)} social)")


if __name__ == "__main__":
    main()
