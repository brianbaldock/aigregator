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
STOP = set("a an the of to in on at for with and or but is are was were be been being "
           "this that these those it its as by from how why what who when where "
           "new says will can may could would should has have had do does did".split())

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

# -------- cluster + score --------
def cluster_and_score(items):
    # Greedy clustering: each item joins the first existing cluster whose
    # representative title shares ≥3 meaningful tokens (Jaccard ≥ ~0.4).
    # Otherwise it seeds a new cluster.
    clusters = []  # list of {"tokens": set, "items": [..]}
    for it in items:
        toks = title_tokens(it["title"])
        placed = False
        if len(toks) >= 3:
            for c in clusters:
                shared = toks & c["tokens"]
                # require 3 shared tokens AND >= 40% of smaller set
                smaller = min(len(toks), len(c["tokens"]))
                if len(shared) >= 3 and smaller and (len(shared) / smaller) >= 0.4:
                    c["items"].append(it)
                    c["tokens"] |= toks  # accrete vocabulary so chains hold
                    placed = True
                    break
        if not placed:
            clusters.append({"tokens": toks or {it["url"]}, "items": [it]})

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

    # drop garbage: no title, no url, or obvious archive
    items = [i for i in items if i["title"] and i["url"] and i["domain"] not in ("web.archive.org",)]

    scored = cluster_and_score(items)

    # Section quotas: news ranks dominate, but reserve seats so the community
    # tier (Reddit/Bsky/HN) and research tier (arXiv) always appear in the
    # digest regardless of credibility score.
    SOCIAL_QUOTA = 15   # Reddit + Bsky + HN combined
    SUB_QUOTAS = {"reddit": 6, "bsky": 4, "hn": 5}
    RESEARCH_QUOTA = 5  # arXiv

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
    remaining = max(0, args.limit - len(social_pick) - len(research_pick))
    news_pick = news[:remaining]

    # Final order: news first (already sorted by score), then research, then social
    merged = news_pick + research_pick + social_pick

    # stats
    by_dom = defaultdict(int)
    for m in merged: by_dom[m["domain"]] += 1
    wire_count = sum(by_dom[d] for d in WIRE_DOMAINS)
    cross = sum(1 for m in merged if "cross_source" in m["flags"])
    print(f"[merge_score] tiers: news={len(news_pick)} research={len(research_pick)} social={len(social_pick)}")

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
