#!/usr/bin/env python3
"""fetch_opensource.py — GitHub trending + watchlist + HuggingFace trending.

Canonical gather step for the Open Source & Emerging section. Writes
/tmp/aig/opensource.json with three buckets:

    {"github_trending": [...], "github_watchlist": [...], "hf_trending": [...]}

Consumed by merge_score.load_opensource(), which emits these as tier="opensource"
items so they auto-route to the 🌱 Open Source & Emerging section without needing
a curation overlay (same pattern as tier="research" -> Research section).

No LLM. Stdlib + urllib only. Honors $GITHUB_TOKEN if present (raises the
unauthenticated 60 req/hr ceiling and lets the topic sweep run at 1s spacing
instead of 7s). Each bucket fails independently — a GitHub outage still lets HF
items through, and vice versa.

Usage:
    GITHUB_TOKEN=... python scripts/fetch_opensource.py
    python scripts/fetch_opensource.py            # unauthenticated, slower
"""
import json, os, sys, time
from datetime import datetime, timezone, timedelta
import urllib.request, urllib.parse

NOW = datetime.now(timezone.utc)
TOKEN = os.environ.get("GITHUB_TOKEN", "").strip()
OUT = os.environ.get("AIG_OPENSOURCE_OUT", "/tmp/aig/opensource.json")

# Orgs we explicitly watch for fresh, non-trivial pushes regardless of trending rank.
WATCH_ORGS = ["NousResearch", "openclaw"]
# Topic sweep for trending repos pushed in the last week.
TRENDING_TOPICS = ["llm", "agent", "rag", "fine-tuning", "inference", "vector-database"]


def gh_get(url, timeout=25):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "aigregator/1.0"}
    if TOKEN:
        headers["Authorization"] = f"token {TOKEN}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def get_json(url, timeout=25, headers=None):
    h = {"User-Agent": "aigregator/1.0", "Accept": "application/json"}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def parse_dt(s):
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def github_trending():
    week_ago = (NOW - timedelta(days=7)).strftime("%Y-%m-%d")
    cand = {}
    for t in TRENDING_TOPICS:
        q = f"topic:{t} pushed:>{week_ago}"
        try:
            qq = urllib.parse.quote(q)
            url = f"https://api.github.com/search/repositories?q={qq}&sort=stars&order=desc&per_page=15"
            d = gh_get(url)
            for repo in d.get("items", []):
                stars = repo.get("stargazers_count", 0)
                forks = repo.get("forks_count", 0)
                pushed = parse_dt(repo.get("pushed_at", ""))
                desc = repo.get("description")
                lic = (repo.get("license") or {}).get("spdx_id")
                # Require a description and a real OSS license; skip vanity/empty repos.
                if not desc or not lic or lic == "NOASSERTION":
                    continue
                if stars < 100:
                    continue
                # forks/stars ratio filters star-farmed repos with no real engagement.
                if stars and (forks / stars) < 0.15:
                    continue
                if not pushed or pushed < (NOW - timedelta(days=7)):
                    continue
                fn = repo["full_name"]
                cand.setdefault(fn, {
                    "full_name": fn, "description": desc[:200],
                    "url": repo["html_url"], "stars": stars, "forks": forks,
                    "ratio": round(forks / stars, 2) if stars else 0,
                    "pushed_at": repo.get("pushed_at", ""),
                    "topics": repo.get("topics", [])[:5],
                    "kind": "trending",
                })
            print(f"[gh] topic:{t}: {len(d.get('items', []))} raw")
        except Exception as ex:
            print(f"[gh] topic:{t} ERR={str(ex)[:100]}", file=sys.stderr)
        time.sleep(7 if not TOKEN else 1)
    # watchlist orgs — surface at most one fresh, non-trivial repo per org
    watch = []
    for org in WATCH_ORGS:
        try:
            url = f"https://api.github.com/orgs/{org}/repos?sort=pushed&direction=desc&per_page=10"
            d = gh_get(url)
            for repo in (d if isinstance(d, list) else []):
                pushed = parse_dt(repo.get("pushed_at", ""))
                stars = repo.get("stargazers_count", 0)
                if pushed and pushed >= (NOW - timedelta(hours=48)) and stars >= 25:
                    watch.append({
                        "full_name": repo["full_name"],
                        "description": (repo.get("description") or "")[:200],
                        "url": repo["html_url"], "stars": stars,
                        "pushed_at": repo.get("pushed_at", ""),
                        "kind": "watchlist",
                    })
                    break  # at most one per org
            print(f"[gh] watchlist {org}: ok")
        except Exception as ex:
            print(f"[gh] watchlist {org} ERR={str(ex)[:100]}", file=sys.stderr)
        time.sleep(7 if not TOKEN else 1)
    trending = sorted(cand.values(), key=lambda x: -x["stars"])[:5]
    return trending, watch


def hf_trending():
    out = []
    for kind, base in [("model", "models"), ("dataset", "datasets")]:
        try:
            url = f"https://huggingface.co/api/{base}?sort=likes7d&direction=-1&limit=20"
            d = get_json(url)
            if not isinstance(d, list) or not d:
                url = f"https://huggingface.co/api/{base}?sort=downloads&direction=-1&limit=20"
                d = get_json(url)
            for m in d[:20]:
                likes = m.get("likes", 0) or 0
                lm = parse_dt(m.get("lastModified", ""))
                if likes < 50:
                    continue
                if lm and lm < (NOW - timedelta(days=7)):
                    continue
                out.append({
                    "id": m.get("id", ""), "kind": kind,
                    "likes": likes, "downloads": m.get("downloads", 0),
                    "pipeline_tag": m.get("pipeline_tag", ""),
                    "url": f"https://huggingface.co/{m.get('id','')}",
                    "lastModified": m.get("lastModified", ""),
                })
            print(f"[hf] {base}: collected")
        except Exception as ex:
            print(f"[hf] {base} ERR={str(ex)[:100]}", file=sys.stderr)
        time.sleep(1)
    out.sort(key=lambda x: -x["likes"])
    return out[:2]


def main():
    trending, watch = github_trending()
    hf = hf_trending()
    result = {"github_trending": trending, "github_watchlist": watch, "hf_trending": hf}
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(result, open(OUT, "w"), ensure_ascii=False, indent=2)
    print(f"[opensource] wrote {len(trending)} trending + {len(watch)} watchlist + {len(hf)} hf -> {OUT}")


if __name__ == "__main__":
    main()
