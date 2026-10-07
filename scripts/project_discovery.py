"""Load GitHub projects shared in r/BestGitHubRepos for editorial review."""
from __future__ import annotations

import json
import os
import re
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlparse
from scoring_policy import score_item

PROJECT_SUB = "BestGitHubRepos"
PROJECT_SOURCE = "r/BestGitHubRepos"
GITHUB_RESERVED_ROOTS = {
    "about", "apps", "collections", "contact", "discussions", "events", "explore",
    "features", "gist", "gists", "github", "issues", "join", "login", "marketplace",
    "new", "notifications", "orgs", "organizations", "pricing", "pulls", "search",
    "security", "settings", "site", "sponsors", "stars", "teams", "topics", "trending",
    "users",
}


def _repo_identity(url: str) -> str | None:
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    if (parsed.scheme not in {"http", "https"} or parsed.hostname != "github.com"
            or parsed.username is not None or parsed.password is not None or port is not None):
        return None
    raw_parts = [part for part in parsed.path.split("/") if part]
    if len(raw_parts) != 2:
        return None
    parts = [unquote(part) for part in raw_parts]
    if any(part in {".", ".."} or "/" in part or "\\" in part for part in parts):
        return None
    if not all(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", part) for part in parts):
        return None
    if parts[0].lower() in GITHUB_RESERVED_ROOTS:
        return None
    return "/".join(parts)


def _current_date(value, now):
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    dt = dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    return dt if now - timedelta(hours=24) <= dt <= now else None


def _excerpt(row):
    text = re.sub(r"\s+", " ", str(row.get("title") or row.get("summary") or "")).strip()
    return text[:400]


def load_projects(indir: str, now: datetime | None = None) -> list[dict]:
    """Return unique, current repository candidates without asserting AI relevance."""
    now = now or datetime.now(timezone.utc)
    now = now.replace(tzinfo=timezone.utc) if now.tzinfo is None else now.astimezone(timezone.utc)
    try:
        with open(os.path.join(indir, "reddit_items.json"), encoding="utf-8") as f:
            rows = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(rows, list):
        return []

    projects = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or row.get("subreddit") != PROJECT_SUB:
            continue
        published = _current_date(row.get("published"), now)
        urls = row.get("project_urls")
        if not published or not isinstance(urls, list):
            continue
        for url in urls:
            if not isinstance(url, str):
                continue
            identity = _repo_identity(url)
            if not identity or identity.lower() in seen:
                continue
            seen.add(identity.lower())
            source = f"GitHub:{identity}"
            project = {
                "url": url, "source": source, "domain": "github.com",
                "credibility": 2, "source_count": 1,
                "source_domains": ["github.com"],
                "source_urls": [{"url": url, "domain": "github.com", "source": source}],
                "sources": [source], "flags": [], "sentiment": 0, "sdot": 0,
                "tier": "projects", "section": "projects", "themes": [], "via_kagi": False,
                "published": published.isoformat(), "published_kind": "discovery_post",
                "discovery_url": row.get("url", ""), "discovery_source": PROJECT_SOURCE,
                "requires_ai_review": True, "title": identity,
                "summary": f"Shared on {PROJECT_SOURCE}: {_excerpt(row)}",
            }
            project['score'] = score_item(project)
            projects.append(project)
    return projects
