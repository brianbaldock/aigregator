#!/usr/bin/env python3
"""
Kagi API helper for AIgregator (v1 Search + Extract).

Subcommands:
  search  <query> [--limit N] [--days N]   — POST /api/v1/search
                                              --days filters out results older
                                              than N days based on the result's
                                              `time` field (results with no
                                              date are kept).
  extract <url> [<url> ...]                — POST /api/v1/extract (1-10 URLs)
  summarize <url> [engine]                 — v0 summarize (disabled by default;
                                              set KAGI_SUMMARIZER_ENABLED=1)

Reads token from ~/.config/aigregator/secrets.env (KAGI_API_TOKEN_V1=...).
Falls back to KAGI_API_TOKEN for v0 summarize only.

Outputs JSON to stdout. Exits 0 on success or API-level errors (so the
calling agent can decide what to do); exits 2 on missing token or HTTP
failure.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SECRETS = Path.home() / ".config" / "aigregator" / "secrets.env"
BASE_V1 = "https://kagi.com/api/v1"
BASE_V0 = "https://kagi.com/api/v0"


def load_token(key: str) -> str | None:
    if not SECRETS.exists():
        return None
    for line in SECRETS.read_text().splitlines():
        line = line.strip()
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def _post(base: str, path: str, body: dict, token_key: str) -> dict:
    token = load_token(token_key)
    if not token:
        print(json.dumps({"error": "no_token", "msg": f"missing {token_key} in {SECRETS}"}))
        sys.exit(2)
    req = urllib.request.Request(
        f"{base}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except Exception as e:
        print(json.dumps({"error": "http_failure", "msg": str(e)}))
        sys.exit(2)


def _get(base: str, path: str, params: dict, token_key: str) -> dict:
    token = load_token(token_key)
    if not token:
        print(json.dumps({"error": "no_token", "msg": f"missing {token_key} in {SECRETS}"}))
        sys.exit(2)
    url = f"{base}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bot {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(json.dumps({"error": "http_failure", "msg": str(e)}))
        sys.exit(2)


def _filter_by_age(results: list[dict], days: int) -> list[dict]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    kept = []
    for r in results:
        t = r.get("time")
        if not t:
            kept.append(r)  # no date — let caller decide
            continue
        try:
            # Kagi returns ISO-8601 with Z; normalize.
            ts = datetime.fromisoformat(t.replace("Z", "+00:00"))
            if ts >= cutoff:
                kept.append(r)
        except ValueError:
            kept.append(r)
    return kept


def cmd_search(query: str, limit: int, days: int | None) -> None:
    body: dict = {"query": query, "limit": limit}
    resp = _post(BASE_V1, "/search", body, "KAGI_API_TOKEN_V1")
    if days and isinstance(resp.get("data"), dict):
        search = resp["data"].get("search") or []
        before = len(search)
        resp["data"]["search"] = _filter_by_age(search, days)
        resp.setdefault("_aigregator", {})["recency_filter"] = {
            "days": days, "kept": len(resp["data"]["search"]), "dropped": before - len(resp["data"]["search"])
        }
    print(json.dumps(resp, indent=2))


def cmd_extract(urls: list[str]) -> None:
    if not 1 <= len(urls) <= 10:
        print(json.dumps({"error": "bad_args", "msg": "extract takes 1-10 URLs"}))
        sys.exit(2)
    body = {"pages": [{"url": u} for u in urls]}
    resp = _post(BASE_V1, "/extract", body, "KAGI_API_TOKEN_V1")
    print(json.dumps(resp, indent=2))


def cmd_summarize(url: str, engine: str = "cecil") -> None:
    # v0 summarize stays gated for cost.
    enabled = os.environ.get("KAGI_SUMMARIZER_ENABLED") == "1"
    if not enabled and SECRETS.exists():
        for line in SECRETS.read_text().splitlines():
            if line.strip().startswith("KAGI_SUMMARIZER_ENABLED="):
                val = line.split("=", 1)[1].strip().strip('"').strip("'")
                if val == "1":
                    enabled = True
                    break
    if not enabled:
        print(json.dumps({"error": "disabled", "msg": "summarize is disabled for cost control; set KAGI_SUMMARIZER_ENABLED=1 in ~/.config/aigregator/secrets.env to enable"}))
        sys.exit(2)
    resp = _get(BASE_V0, "/summarize", {"url": url, "summary_type": "summary", "engine": engine}, "KAGI_API_TOKEN")
    print(json.dumps(resp, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser(prog="kagi.py", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("search", help="Kagi v1 search")
    sp.add_argument("query")
    sp.add_argument("--limit", type=int, default=10)
    sp.add_argument("--days", type=int, default=None,
                    help="Only keep results younger than N days (by result.time)")

    ep = sub.add_parser("extract", help="Kagi v1 extract")
    ep.add_argument("urls", nargs="+")

    smp = sub.add_parser("summarize", help="Kagi v0 summarize (gated)")
    smp.add_argument("url")
    smp.add_argument("engine", nargs="?", default="cecil")

    args = ap.parse_args()
    if args.cmd == "search":
        cmd_search(args.query, args.limit, args.days)
    elif args.cmd == "extract":
        cmd_extract(args.urls)
    elif args.cmd == "summarize":
        cmd_summarize(args.url, args.engine)
    return 0


if __name__ == "__main__":
    sys.exit(main())
