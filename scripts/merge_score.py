#!/usr/bin/env python3
"""
merge_score.py — canonical merge + cluster + score for AIgregator.

Reads all per-source JSON dumps from /tmp/aig/ (Kagi wire searches, RSS, Reddit,
Bluesky, arXiv, HN, Polymarket), normalizes them into a single schema, clusters
by normalized title across domains, scores with credibility-weighted sentiment,
and writes /tmp/aig/digest_items.json for build.py.

Why this exists: prior cron runs silently rebuilt scoring in /tmp and skipped
the Kagi→digest merge entirely. As a result Reuters/AP/Bloomberg/WSJ items
fetched via Kagi v1 never made it into digests. This script is the single
committed merge step.

Usage:
    python scripts/merge_score.py [--in /tmp/aig] [--out /tmp/aig/digest_items.json]
"""
from __future__ import annotations
import argparse, glob, json, os, re, sys
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import urlparse

# -------- credibility map (domain → 1..5) --------
CRED = {
    "reuters.com": 5, "apnews.com": 5, "bloomberg.com": 5, "wsj.com": 5,
    "ft.com": 5, "bbc.com": 5, "bbc.co.uk": 5, "theguardian.com": 5,
    "nytimes.com": 5, "washingtonpost.com": 5, "economist.com": 5,
    "nature.com": 5, "science.org": 5, "arxiv.org": 4,
    "techcrunch.com": 4, "theverge.com": 4, "wired.com": 4, "arstechnica.com": 4,
    "engadget.com": 3, "venturebeat.com": 3, "zdnet.com": 3,
    "openai.com": 4, "anthropic.com": 4, "deepmind.com": 4, "deepmind.google": 4,
    "ai.meta.com": 4, "ai.google": 4, "research.google": 4, "blogs.microsoft.com": 4,
    "huggingface.co": 4, "github.com": 3, "news.ycombinator.com": 3,
    "lesswrong.com": 3, "alignmentforum.org": 3,
    "bsky.app": 2, "reddit.com": 2, "medium.com": 2, "substack.com": 2,
    "web.archive.org": 1,
}

WIRE_DOMAINS = {"reuters.com", "apnews.com", "bloomberg.com", "wsj.com"}

# Stopwords for title normalization (cross-source clustering)
STOP = set("a an the of to in on at for for with and or but is are was were be been being "
           "this that these those it its as by from how why what who when where "
           "new says will can may could would should has have had do does did "
           "ai".split())

# Named entities — orgs/people that signal "same story" when shared across wires.
# Lowercase, multi-word entries are matched as substrings of the lowercased title.
KNOWN_ENTITIES = {
    "anthropic", "openai", "deepmind", "google", "alphabet", "microsoft", "meta",
    "nvidia", "amazon", "apple", "tesla", "x.ai", "mistral", "huggingface",
    "perplexity", "character.ai", "cohere", "inflection", "stability",
    "claude", "gpt", "gemini", "llama", "grok", "copilot", "siri",
    "trump", "biden", "altman", "musk", "huang", "amodei", "hassabis",
    "krishnan", "vance", "sacks", "macron", "sunak",
    "fbi", "doj", "ftc", "sec", "eu", "ec", "ofcom", "fda", "uk", "white house",
    "reuters", "bloomberg",  # used in title-based clustering too
}

# Action verbs — when two titles share an entity AND any of these, they're
# almost certainly covering the same news event from different angles.
ACTION_VERBS = {
    "launches", "launch", "releases", "release", "announces", "announce",
    "unveils", "unveil", "raises", "raised", "funds", "funded", "acquires",
    "acquired", "sues", "sued", "files", "filed", "signs", "signed", "orders",
    "ordered", "blocks", "blocked", "approves", "approved", "passes", "passed",
    "warns", "warned", "urges", "urged", "calls", "called", "demands",
    "demanded", "halts", "halt", "halted", "pauses", "pause", "paused",
    "invests", "invested", "buys", "bought", "merges", "merged",
    "ipo", "ipos", "deal", "partnership", "agreement", "lawsuit", "indicted",
    "fired", "resigns", "exits", "joins", "hires", "hired",
    # synonym-cluster markers below also get normalized into one of these
    # buckets when computing match — see VERB_SYNONYMS.
}

# Verbs that mean roughly the same thing for clustering purposes. When two
# titles share an entity AND each has a verb from the SAME synonym group,
# they cluster. Add new groups conservatively — false-positive merges hurt
# more than missed clusters.
VERB_SYNONYMS = [
    {"halt", "halts", "halted", "pause", "pauses", "paused", "stop", "stops",
     "stopped", "slowdown", "slow", "freeze", "moratorium"},
    {"urges", "urge", "urged", "calls", "call", "called", "demands", "demand",
     "demanded", "warns", "warned", "warn", "tells", "told"},
    {"launches", "launch", "launched", "releases", "release", "released",
     "announces", "announce", "announced", "unveils", "unveiled", "ships",
     "shipped", "rolls", "rolled", "debuts"},
    {"raises", "raised", "funds", "funded", "secures", "secured", "closes",
     "closed", "completes", "completed"},
    {"acquires", "acquired", "buys", "bought", "purchases", "purchased"},
    {"sues", "sued", "files", "filed", "lawsuit", "indicted", "charged",
     "subpoena", "subpoenaed"},
    {"signs", "signed", "orders", "ordered", "approves", "approved", "passes",
     "passed", "enacts", "enacted"},
    {"blocks", "blocked", "bans", "banned", "restricts", "restricted",
     "prohibits", "prohibited", "rejects", "rejected"},
    {"invests", "invested", "investment", "stakes", "stake", "deal",
     "partnership", "agreement"},
    {"resigns", "resigned", "exits", "exited", "departs", "departed",
     "leaves", "left", "quits", "quit"},
    {"hires", "hired", "joins", "joined", "names", "named", "appoints",
     "appointed", "promotes", "promoted"},
]


def _verb_group(action: str) -> int:
    """Return the synonym-group index for an action verb, or -1 if standalone."""
    for i, group in enumerate(VERB_SYNONYMS):
        if action in group:
            return i
    return -1


def actions_match(a1: set, a2: set) -> bool:
    """Two action sets match if they share a literal verb OR they share a
    verb synonym group."""
    if a1 & a2:
        return True
    g1 = {_verb_group(v) for v in a1 if _verb_group(v) >= 0}
    g2 = {_verb_group(v) for v in a2 if _verb_group(v) >= 0}
    return bool(g1 & g2)


def extract_entities(title: str) -> set:
    """Return the set of KNOWN_ENTITIES that appear in this title (lowercased,
    substring match for multi-word entities)."""
    low = (title or "").lower()
    found = set()
    for ent in KNOWN_ENTITIES:
        if ent in low:
            # require word boundary for short single-word entities to avoid
            # 'meta' matching 'metamorphosis'
            if " " in ent:
                found.add(ent)
            elif re.search(rf"\b{re.escape(ent)}\b", low):
                found.add(ent)
    return found


def extract_actions(title: str) -> set:
    """Return action verbs present in this title."""
    low = (title or "").lower()
    # Union of all explicit action verbs (literal list) and all synonym group members
    all_actions = set(ACTION_VERBS)
    for grp in VERB_SYNONYMS:
        all_actions |= grp
    return {v for v in all_actions if re.search(rf"\b{re.escape(v)}\b", low)}


POS = {"breakthrough","wins","launch","launches","raises","raised","grows","beats",
       "open-source","opens","funds","invests","accelerates","approves","passes","agrees"}
NEG = {"layoffs","fired","lawsuit","sued","fraud","scam","outage","breach","hack","hacked",
       "down","fails","failed","blocks","banned","ban","fines","fined","kills","killed",
       "warns","threat","risk","crisis","collapse","resigns","probe","investigation"}

# -------- helpers --------
def domain_of(url: str) -> str:
    try:
        h = urlparse(url).hostname or ""
        h = h.lower()
        if h.startswith("www."): h = h[4:]
        return h
    except Exception:
        return ""

def cred_of(domain: str) -> int:
    if domain in CRED: return CRED[domain]
    # subdomain fallback
    parts = domain.split(".")
    for i in range(1, len(parts)):
        cand = ".".join(parts[i:])
        if cand in CRED: return CRED[cand]
    return 2

def title_tokens(t: str) -> set:
    t = (t or "").lower()
    t = re.sub(r"[^\w\s]", " ", t, flags=re.UNICODE)
    return {w for w in t.split() if w not in STOP and len(w) > 2}

def parse_pub(s) -> str:
    if not s: return ""
    if isinstance(s, (int, float)):
        try: return datetime.fromtimestamp(s, tz=timezone.utc).isoformat()
        except Exception: return ""
    return str(s)

def sentiment(title: str, desc: str) -> int:
    text = f"{title} {desc}".lower()
    p = sum(1 for w in POS if w in text)
    n = sum(1 for w in NEG if w in text)
    if p == 0 and n == 0: return 0
    return max(-3, min(3, p - n))

# -------- loaders (each returns list[dict] in unified schema) --------
def _item(source, cred, title, url, desc, pub, via_kagi=False):
    return {
        "source": source,
        "credibility": cred,
        "title": (title or "").strip(),
        "url": url,
        "domain": domain_of(url),
        "summary": (desc or "").strip()[:400],
        "published": parse_pub(pub),
        "via_kagi": via_kagi,
    }

# Topic/hub landing-page URL pathnames the Kagi wire searches keep surfacing.
# These get presented as if they were stories — they're not. A real wire story
# either has a date segment (/2026/05/27/) or a long hyphenated slug ending in
# -YYYY-MM-DD, or for AP an article id like "/article/..."-suffixed hash.
import re as _re

_DATE_SEG = _re.compile(r"/(?:19|20)\d{2}[/-]")        # /2026/ or /2026-
_DATED_SLUG = _re.compile(r"-(?:19|20)\d{2}-\d{2}-\d{2}")  # -2026-05-27
_AP_ARTICLE = _re.compile(r"/article/[\w-]+-?[0-9a-f]{8,}")  # AP article id
_BLOOMBERG_ARTICLE = _re.compile(r"/news/(?:articles|features|newsletters|videos|opinion)/")
_WSJ_ARTICLE = _re.compile(r"/(?:tech|ai|business|finance|economy|world|markets|politics)/.+-[0-9a-f]{6,}")

def _looks_like_story(url: str, dom: str) -> bool:
    """Filter out hub/landing/topic pages from wire-service URLs."""
    path = url.split("?")[0].split("#")[0]
    # Trim domain
    if "://" in path:
        path = "/" + path.split("/", 3)[-1] if path.count("/") >= 3 else "/"
    if _DATE_SEG.search(path) or _DATED_SLUG.search(path):
        return True
    if dom == "apnews.com" and _AP_ARTICLE.search(path):
        return True
    if dom == "bloomberg.com" and _BLOOMBERG_ARTICLE.search(path):
        return True
    if dom == "wsj.com" and _WSJ_ARTICLE.search(path):
        return True
    # Path too short = almost certainly a hub: /technology/ , /ai/ , /
    segments = [s for s in path.split("/") if s]
    if len(segments) <= 2:
        return False
    # Final fallback: require a long descriptive slug (≥4 hyphens) somewhere in path
    if any(s.count("-") >= 4 for s in segments):
        return True
    return False


# Sponsored-content / branded-content fingerprints. These are NOT news stories
# even when surfaced by Kagi from wire-service domains. Drop pre-cluster.
SPONSORED_HOST_PREFIXES = ("plus.reuters.com",)  # Reuters' branded content arm
SPONSORED_TITLE_PHRASES = (
    "content studios",  # Reuters/Bloomberg sponsored series banner
    "case studies",     # Reuters branded
    "branded content",
    "paid content",
    "in partnership with",
    "sponsored content",
    "advertorial",
)


def _is_sponsored(url: str, title: str, summary: str) -> bool:
    """Return True if the item is branded/sponsored content."""
    lower_url = (url or "").lower()
    if any(host in lower_url for host in SPONSORED_HOST_PREFIXES):
        return True
    text = f"{(title or '')} {(summary or '')[:400]}".lower()
    return any(p in text for p in SPONSORED_TITLE_PHRASES)

def load_kagi(indir: str):
    out = []
    for fp in sorted(glob.glob(os.path.join(indir, "kagi", "*.json"))):
        try:
            d = json.load(open(fp))
        except Exception:
            continue
        results = []
        data = d.get("data")
        if isinstance(data, dict) and isinstance(data.get("search"), list):
            results = data["search"]
        elif isinstance(data, list):
            results = data
        for r in results:
            url = r.get("url") or ""
            if not url: continue
            dom = domain_of(url)
            # Drop hub/topic landing pages — they shouldn't appear as stories
            if dom in WIRE_DOMAINS and not _looks_like_story(url, dom):
                continue
            # Drop branded/sponsored content (KPMG Content Studios, Reuters Plus, etc.)
            if _is_sponsored(url, r.get("title", ""), r.get("snippet", "")):
                continue
            # wire credibility override
            cred = 5 if dom in WIRE_DOMAINS else cred_of(dom)
            src = "Reuters" if dom == "reuters.com" else \
                  "AP News" if dom == "apnews.com" else \
                  "Bloomberg" if dom == "bloomberg.com" else \
                  "WSJ" if dom == "wsj.com" else \
                  f"Kagi:{dom}"
            out.append(_item(src, cred, r.get("title"), url,
                             r.get("snippet"), r.get("time"), via_kagi=True))
    return out

def load_rss(indir: str):
    fp = os.path.join(indir, "rss_items.json")
    if not os.path.exists(fp): return []
    out = []
    for r in json.load(open(fp)):
        out.append(_item(r.get("source","RSS"), r.get("credibility", r.get("cred", 3)),
                         r.get("title"), r.get("url") or r.get("link",""),
                         r.get("summary") or r.get("desc",""),
                         r.get("published") or r.get("pub")))
    return out

def load_arxiv(indir: str):
    fp = os.path.join(indir, "arxiv_items.json")
    if not os.path.exists(fp): return []
    out = []
    for r in json.load(open(fp)):
        cat = r.get("category") or r.get("cat","")
        out.append(_item(r.get("source") or f"arXiv:{cat}", r.get("credibility", 4),
                         r.get("title"), r.get("url") or r.get("link",""),
                         r.get("summary") or r.get("desc",""),
                         r.get("published")))
    return out

def load_reddit(indir: str):
    fp = os.path.join(indir, "reddit_items.json")
    if not os.path.exists(fp): return []
    out = []
    for r in json.load(open(fp)):
        sub = r.get("subreddit") or r.get("sub","")
        out.append(_item(f"r/{sub}", r.get("credibility", 2),
                         r.get("title"), r.get("url",""),
                         r.get("summary",""), r.get("published")))
    return out

def load_bsky(indir: str):
    fp = os.path.join(indir, "bsky_items.json")
    if not os.path.exists(fp): return []
    out = []
    for r in json.load(open(fp)):
        text = r.get("summary") or r.get("text","") or r.get("title","")
        title = r.get("title") or ((text[:120] + "…") if len(text) > 120 else text)
        out.append(_item(f"bsky:{r.get('handle','')}", r.get("credibility", 2),
                         title, r.get("url",""), text, r.get("published")))
    return out

def load_hn(indir: str):
    out = []
    for fp in sorted(glob.glob(os.path.join(indir, "hn*.json"))):
        try: d = json.load(open(fp))
        except Exception: continue
        # Two shapes seen in the wild:
        #   1) Algolia raw: {"hits": [...]} — each hit has objectID/title/url/created_at
        #   2) Pre-normalized list of items the agent dumped this morning
        if isinstance(d, dict):
            hits = d.get("hits") or []
            for h in hits:
                url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID','')}"
                out.append(_item("HN", 3, h.get("title"), url, "",
                                 h.get("created_at")))
        elif isinstance(d, list):
            for h in d:
                if not isinstance(h, dict): continue
                url = h.get("url") or ""
                title = h.get("title") or ""
                if not title: continue
                out.append(_item("HN", 3, title, url, h.get("summary","") or "",
                                 h.get("created_at") or h.get("published")))
    return out

def load_opensource(indir: str):
    """Load GitHub trending/watchlist + HuggingFace trending from opensource.json.

    These are discrete repos/models, NOT news stories, so they deliberately
    bypass cluster_and_score() (see main()): a trending repo that happens to
    share title tokens with a news headline must not be absorbed into that news
    cluster and silently dropped. We emit them with tier="opensource" so they
    auto-route to the 🌱 Open Source & Emerging section without a curation
    overlay (mirrors how tier="research" routes to Research).

    Returns fully-formed canonical items (the same shape cluster_and_score
    emits) so write_digest can render them directly.
    """
    fp = os.path.join(indir, "opensource.json")
    try:
        d = json.load(open(fp))
    except Exception:
        return []
    out = []

    # Conservative noise gate: GitHub's topic sweep occasionally surfaces huge
    # general-knowledge repos that opportunistically tag themselves ai/agent
    # (interview guides, awesome-lists, roadmaps, books). These aren't AI
    # tooling. Skip a repo only when its name/description clearly matches a
    # collection/guide fingerprint — keep it tight to avoid dropping real tools.
    _NOISE_RE = re.compile(
        r"(awesome[- ]|interview|面试|roadmap|cheat[- ]?sheet|"
        r"\bguide\b|教程|tutorial|free[- ]?books?|学习|developer[- ]roadmap|"
        r"system[- ]design[- ]primer|coding[- ]interview)",
        re.I,
    )

    def _is_noise(full_name, desc):
        blob = f"{full_name} {desc}"
        return bool(_NOISE_RE.search(blob))

    def _canon(source, cred, title, url, desc, os_kind):
        # Build a render-ready item without going through clustering.
        it = _item(source, cred, title, url, desc, None)
        it["sentiment"] = 0          # repos/models are neutral; keep them out of sentiment math
        it["sdot"] = 0
        it["source_urls"] = [{"domain": it["domain"], "url": url, "source": source}]
        it["source_domains"] = [it["domain"]] if it["domain"] else []
        it["sources"] = [source]
        it["source_count"] = 1
        it["flags"] = []
        it["section"] = "opensource"
        it["themes"] = []
        it["tier"] = "opensource"
        it["os_kind"] = os_kind  # "watchlist" | "trending" | "hf" — drives diversity pick
        # Score by credibility so the per-section cap keeps the strongest signals.
        it["score"] = cred * 2
        return it

    for r in d.get("github_trending", []) if isinstance(d, dict) else []:
        fn = r.get("full_name") or ""
        if not fn or not r.get("url"):
            continue
        desc = r.get("description", "") or ""
        if _is_noise(fn, desc):
            continue  # skip general-knowledge/guide mega-repos
        stars = r.get("stars", 0)
        topics = ", ".join(r.get("topics", [])[:3])
        meta = f"{stars:,}★ on GitHub" + (f" · {topics}" if topics else "")
        summary = f"{desc} ({meta})." if desc else f"Trending on GitHub ({meta})."
        out.append(_canon(f"GitHub:{fn}", 3, fn, r["url"], summary, "trending"))

    for r in d.get("github_watchlist", []) if isinstance(d, dict) else []:
        fn = r.get("full_name") or ""
        if not fn or not r.get("url"):
            continue
        stars = r.get("stars", 0)
        desc = r.get("description", "") or ""
        summary = f"{desc} ({stars:,}★, fresh push)." if desc else f"Fresh push ({stars:,}★)."
        # Watchlist orgs get a credibility bump so they survive the section cap.
        out.append(_canon(f"GitHub:{fn}", 4, fn, r["url"], summary, "watchlist"))

    for r in d.get("hf_trending", []) if isinstance(d, dict) else []:
        hid = r.get("id") or ""
        if not hid or not r.get("url"):
            continue
        likes = r.get("likes", 0)
        dls = r.get("downloads", 0)
        tag = r.get("pipeline_tag", "") or r.get("kind", "model")
        bits = []
        if likes: bits.append(f"{likes:,} likes")
        if dls: bits.append(f"{dls:,} downloads")
        meta = ", ".join(bits) or "trending"
        summary = f"Trending on HuggingFace · {tag} ({meta})."
        out.append(_canon(f"HF:{hid}", 3, hid, r["url"], summary, "hf"))

    # Dedup by URL — a repo can surface in both watchlist and trending
    # (e.g. a watchlist org repo also trending on stars). Keep the
    # highest-credibility copy (watchlist > trending) so the better label wins.
    best = {}
    for it in out:
        cur = best.get(it["url"])
        if cur is None or it["credibility"] > cur["credibility"]:
            best[it["url"]] = it
    return list(best.values())

# -------- cluster + score --------
def cluster_and_score(items):
    # Greedy clustering with TWO signals (an item joins a cluster if EITHER fires):
    #   (a) Title-token overlap: >=3 shared meaningful tokens AND Jaccard >= 0.4
    #   (b) Entity+action signal: items share at least one KNOWN_ENTITY AND
    #       at least one ACTION_VERB (or share 2+ entities). This catches
    #       wire stories that re-frame the same event with divergent verbs
    #       (e.g. Anthropic "says"/"urges"/"calls"/"warns" about the same pause).
    # Wire-to-wire pairs get the loosened (b) path. Two wires reporting on the
    # same entity-event are almost always the same story.
    clusters = []  # list of {"tokens": set, "entities": set, "items": [..]}
    for it in items:
        toks = title_tokens(it["title"])
        ents = extract_entities(it["title"])
        acts = extract_actions(it["title"])
        placed = False
        is_wire = it.get("domain") in WIRE_DOMAINS
        for c in clusters:
            # Path (a): token-jaccard
            shared = toks & c["tokens"]
            smaller = min(len(toks), len(c["tokens"])) if c["tokens"] else 0
            token_match = (len(shared) >= 3 and smaller and (len(shared) / smaller) >= 0.4)
            # Path (b): entity+action (cross-wire only, to avoid overclustering
            # blogs that just happen to mention the same vendor)
            shared_ents = ents & c["entities"]
            actions_overlap = actions_match(acts, c.get("actions", set()))
            entity_match = False
            c_has_wire = any(g.get("domain") in WIRE_DOMAINS for g in c["items"])
            if is_wire and c_has_wire and shared_ents:
                # Two wires + shared entity. Cluster if any of:
                #   - they share an action verb or synonym (urges/calls/warns; halt/pause)
                #   - they share 2+ entities (Anthropic+Amazon together)
                #   - they share an entity AND a weak token signal (Jaccard >= 0.2)
                if actions_overlap or len(shared_ents) >= 2 or (smaller and len(shared) / smaller >= 0.2):
                    entity_match = True
            if token_match or entity_match:
                c["items"].append(it)
                c["tokens"] |= toks  # accrete vocabulary so chains hold
                c["entities"] |= ents
                c.setdefault("actions", set()).update(acts)
                placed = True
                break
        if not placed:
            clusters.append({
                "tokens": toks or {it["url"]},
                "entities": ents,
                "actions": acts,
                "items": [it],
            })

    # Second pass: merge clusters that share an entity AND an action verb
    # (literal OR synonym group) AND both have ≥1 wire-domain item. Greedy
    # ordering can split the same event into multiple sibling clusters when
    # divergent vocab seeds them (Bloomberg seeds "pause", Reuters seeds
    # "halt" — both Anthropic stories). Two wires sharing entity + verb-bucket
    # is a strong signal.
    changed = True
    while changed:
        changed = False
        for i in range(len(clusters)):
            if changed: break
            for j in range(i + 1, len(clusters)):
                ci, cj = clusters[i], clusters[j]
                shared_ents = ci["entities"] & cj["entities"]
                acts_overlap = actions_match(ci.get("actions", set()), cj.get("actions", set()))
                ci_has_wire = any(g.get("domain") in WIRE_DOMAINS for g in ci["items"])
                cj_has_wire = any(g.get("domain") in WIRE_DOMAINS for g in cj["items"])
                if shared_ents and acts_overlap and ci_has_wire and cj_has_wire:
                    # Merge cj into ci
                    ci["items"].extend(cj["items"])
                    ci["tokens"] |= cj["tokens"]
                    ci["entities"] |= cj["entities"]
                    ci.setdefault("actions", set()).update(cj.get("actions", set()))
                    clusters.pop(j)
                    changed = True
                    break

    merged = []
    for c in clusters:
        group = c["items"]
        # dedup by URL within cluster
        seen = {}
        for it in group:
            seen.setdefault(it["url"], it)
        group = list(seen.values())
        # pick canonical = highest credibility, tiebreak wire-domain, tiebreak longest summary
        group.sort(key=lambda x: (
            -x["credibility"],
            0 if x["domain"] in WIRE_DOMAINS else 1,
            -len(x["summary"] or ""),
        ))
        canonical = dict(group[0])
        domains = sorted({g["domain"] for g in group if g["domain"]})
        sources = sorted({g["source"] for g in group})
        # Preserve all member URLs (one per distinct domain, prefer wire) for source citation
        urls_by_domain = {}
        for g in group:
            d = g["domain"]
            if not d: continue
            # Keep first URL we see per domain (group is already credibility-sorted)
            urls_by_domain.setdefault(d, g["url"])
        canonical["source_urls"] = [{"domain": d, "url": u, "source": next((g["source"] for g in group if g["url"] == u), d)}
                                    for d, u in urls_by_domain.items()]
        canonical["source_domains"] = domains
        canonical["sources"] = sources
        canonical["source_count"] = len(domains)
        s = sentiment(canonical["title"], canonical["summary"])
        canonical["sentiment"] = s
        # credibility-weighted sentiment delta
        canonical["sdot"] = s * canonical["credibility"]
        # base score: credibility + cross-source bonus + freshness placeholder
        cross = max(0, len(domains) - 1)
        canonical["score"] = canonical["credibility"] * 2 + cross * 3 + (1 if canonical["via_kagi"] and canonical["domain"] in WIRE_DOMAINS else 0)
        flags = []
        if len(domains) >= 2: flags.append("cross_source")
        if canonical["domain"] in WIRE_DOMAINS: flags.append("wire")
        if canonical["via_kagi"]: flags.append("kagi")
        canonical["flags"] = flags
        canonical["section"] = "top" if (len(domains) >= 2 or canonical["credibility"] >= 5) else "more"
        canonical["themes"] = []
        merged.append(canonical)

    merged.sort(key=lambda x: (-x["score"], -x["credibility"], x["title"]))
    return merged

# -------- main --------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="indir", default="/tmp/aig")
    ap.add_argument("--out", dest="outfp", default="/tmp/aig/digest_items.json")
    ap.add_argument("--limit", type=int, default=80)
    args = ap.parse_args()

    items = []
    items += load_kagi(args.indir)
    items += load_rss(args.indir)
    items += load_arxiv(args.indir)
    items += load_reddit(args.indir)
    items += load_bsky(args.indir)
    items += load_hn(args.indir)

    # Open-source items (GitHub/HF) are loaded separately and bypass clustering:
    # they're discrete repos/models, not news, and must not be absorbed into a
    # news cluster (token overlap) and silently dropped. They carry tier and
    # section pre-set; we splice them in after news clustering below.
    opensource = load_opensource(args.indir)

    # drop garbage: no title, no url, or obvious archive
    items = [i for i in items if i["title"] and i["url"] and i["domain"] not in ("web.archive.org",)]

    scored = cluster_and_score(items)

    # Section quotas: news ranks dominate, but reserve seats so the community
    # tier (Reddit/Bsky/HN) and research tier (arXiv) always appear in the
    # digest regardless of credibility score.
    SOCIAL_QUOTA = 15   # Reddit + Bsky + HN combined
    SUB_QUOTAS = {"reddit": 6, "bsky": 4, "hn": 5}
    RESEARCH_QUOTA = 5  # arXiv
    OPENSOURCE_QUOTA = 6  # GitHub trending/watchlist + HF trending (write_digest caps display at 4)

    def is_social(it):
        s = it["source"]
        return s.startswith("r/") or s.startswith("bsky:") or s == "HN"
    def social_kind(it):
        s = it["source"]
        if s.startswith("r/"): return "reddit"
        if s.startswith("bsky:"): return "bsky"
        return "hn"
    def is_research(it):
        return it["source"].startswith("arXiv")

    # Tag section so build.py can render groupings
    for it in scored:
        if is_social(it): it["tier"] = "social"
        elif is_research(it): it["tier"] = "research"
        else: it["tier"] = "news"

    news = [i for i in scored if i["tier"] == "news"]
    social = [i for i in scored if i["tier"] == "social"]
    research = [i for i in scored if i["tier"] == "research"]

    # Pull each social sub-source up to its quota, in score order
    social_pick = []
    for kind, q in SUB_QUOTAS.items():
        picks = [i for i in social if social_kind(i) == kind][:q]
        social_pick.extend(picks)
    # Backfill remaining social slots from leftovers (any source)
    chosen_urls = {i["url"] for i in social_pick}
    leftover_social = [i for i in social if i["url"] not in chosen_urls]
    while len(social_pick) < SOCIAL_QUOTA and leftover_social:
        social_pick.append(leftover_social.pop(0))

    research_pick = research[:RESEARCH_QUOTA]
    # Open-source picks are additive (like research): reserve their seats on top
    # of the news budget so trending repos/models never get evicted by a busy
    # news day. They already carry tier/section/score from load_opensource.
    # Diversity-aware selection so HuggingFace isn't crowded out by GitHub
    # (both score similarly): take watchlist first, then interleave the rest by
    # kind round-robin (trending / hf / ...) up to the quota.
    def os_pick(pool, quota):
        from collections import defaultdict as _dd
        by_kind = _dd(list)
        for it in sorted(pool, key=lambda x: -x.get("score", 0)):
            by_kind[it.get("os_kind", "trending")].append(it)
        picked = list(by_kind.pop("watchlist", []))  # always include watched orgs
        # Round-robin across remaining kinds for source diversity
        order = ["hf", "trending"] + [k for k in by_kind if k not in ("hf", "trending")]
        while len(picked) < quota and any(by_kind.get(k) for k in order):
            for k in order:
                if by_kind.get(k):
                    picked.append(by_kind[k].pop(0))
                    if len(picked) >= quota:
                        break
        return picked[:quota]
    opensource_pick = os_pick(opensource, OPENSOURCE_QUOTA)
    remaining = max(0, args.limit - len(social_pick) - len(research_pick))
    news_pick = news[:remaining]

    # Final order: news first (already sorted by score), then research, then
    # open-source, then social.
    merged = news_pick + research_pick + opensource_pick + social_pick

    # stats
    by_dom = defaultdict(int)
    for m in merged: by_dom[m["domain"]] += 1
    wire_count = sum(by_dom[d] for d in WIRE_DOMAINS)
    cross = sum(1 for m in merged if "cross_source" in m["flags"])
    print(f"[merge_score] tiers: news={len(news_pick)} research={len(research_pick)} "
          f"opensource={len(opensource_pick)} social={len(social_pick)}")

    os.makedirs(os.path.dirname(args.outfp), exist_ok=True)
    with open(args.outfp, "w") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"[merge_score] wrote {len(merged)} items → {args.outfp}")
    print(f"[merge_score] wire-service items: {wire_count} "
          f"(reuters={by_dom['reuters.com']} apnews={by_dom['apnews.com']} "
          f"bloomberg={by_dom['bloomberg.com']} wsj={by_dom['wsj.com']})")
    print(f"[merge_score] cross-source clusters (🔥): {cross}")
    if wire_count == 0:
        print("[merge_score] WARNING: zero wire-service items in final digest", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()
