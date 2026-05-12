#!/usr/bin/env python3
"""
Kagi API helper for AIgregator.

Subcommands:
  enrich-news <query>           — pull small-web news results
  enrich-web  <query>           — pull small-web general results
  summarize   <url> [engine]    — summarize a URL (engines: cecil, agnes, daphne, muriel)

Reads token from ~/.config/aigregator/secrets.env (KAGI_API_TOKEN=...).
Outputs JSON to stdout. Exits 0 even on API errors (so the calling
agent can decide what to do); exits 2 on missing token or HTTP failure.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SECRETS = Path.home() / ".config" / "aigregator" / "secrets.env"
BASE = "https://kagi.com/api/v0"


def load_token() -> str | None:
    if not SECRETS.exists():
        return None
    for line in SECRETS.read_text().splitlines():
        line = line.strip()
        if line.startswith("KAGI_API_TOKEN="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def call(path: str, params: dict) -> dict:
    token = load_token()
    if not token:
        print(json.dumps({"error": "no_token", "msg": f"missing {SECRETS}"}))
        sys.exit(2)
    url = f"{BASE}{path}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bot {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read())
    except Exception as e:
        print(json.dumps({"error": "http_failure", "msg": str(e)}))
        sys.exit(2)


def cmd_enrich_news(query: str) -> None:
    r = call("/enrich/news", {"q": query})
    print(json.dumps(r, indent=2))


def cmd_enrich_web(query: str) -> None:
    r = call("/enrich/web", {"q": query})
    print(json.dumps(r, indent=2))


def cmd_summarize(url: str, engine: str = "cecil") -> None:
    r = call("/summarize", {"url": url, "summary_type": "summary", "engine": engine})
    print(json.dumps(r, indent=2))


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 1
    cmd, *args = sys.argv[1:]
    if cmd == "enrich-news":
        cmd_enrich_news(args[0])
    elif cmd == "enrich-web":
        cmd_enrich_web(args[0])
    elif cmd == "summarize":
        engine = args[1] if len(args) > 1 else "cecil"
        cmd_summarize(args[0], engine)
    else:
        print(f"unknown subcommand: {cmd}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
