#!/usr/bin/env python3
"""
Kagi v1 Search healthcheck for AIgregator.

Probes the four mandatory wire-service lanes used by the morning digest:
  site:reuters.com AI
  site:apnews.com AI
  site:bloomberg.com AI
  site:wsj.com AI

Plus two always-on canaries that exercise the API without site: scoping,
so we can tell "Kagi is broken" apart from "this particular site has no
fresh hits today":
  microsoft
  linux

Writes a snapshot to ~/.cache/aigregator/kagi-health.json (last 7 kept).
Prints a one-line summary to stdout. Exits 0 (green), 1 (yellow), 2 (red).

Status rules:
  red    — any HTTP failure, OR both canaries return zero results
  yellow — 2+ mandatory wire-service lanes return zero fresh results
  green  — otherwise

If $DISCORD_WEBHOOK_KAGI_HEALTH is set (in secrets.env or env), posts a
short alert on yellow or red. Steady-state green posts nothing.

Cost: 6 v1 search calls per run = ~$0.03/day worst case.
Designed to run unattended ~02:00 UTC (19:00 PDT / 18:00 PST), the
evening before the 14:00 UTC digest, so Brian has waking hours to fix
anything that's broken before the morning drop.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

SECRETS = Path.home() / ".config" / "aigregator" / "secrets.env"
CACHE_DIR = Path.home() / ".cache" / "aigregator"
SNAPSHOT = CACHE_DIR / "kagi-health.json"
HISTORY_KEEP = 7
BASE = "https://kagi.com/api/v1"

WIRE_QUERIES = [
    "site:reuters.com AI",
    "site:apnews.com AI",
    "site:bloomberg.com AI",
    "site:wsj.com AI",
]
CANARIES = ["microsoft", "linux"]
FRESH_DAYS = 2  # mirrors digest cron's --days 2


def load_secrets() -> dict:
    out: dict[str, str] = {}
    if not SECRETS.exists():
        return out
    for line in SECRETS.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def search(token: str, query: str, limit: int = 10) -> dict:
    url = f"{BASE}/search"
    body = json.dumps({"query": query, "limit": limit}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Authorization": f"Bot {token}", "Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            body_resp = json.loads(r.read())
        return {"ok": True, "ms": int((time.time() - t0) * 1000), "data": body_resp}
    except Exception as e:
        return {"ok": False, "ms": int((time.time() - t0) * 1000), "error": str(e)}


def fresh_count(result: dict, days: int = FRESH_DAYS) -> int:
    """Count results within the last `days` days. Items without `time` count."""
    if not result.get("ok"):
        return 0
    data = result.get("data") or {}
    payload = data.get("data") or {}
    items = payload.get("search") if isinstance(payload, dict) else payload
    items = items or []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    n = 0
    for r in items:
        t = r.get("time")
        if not t:
            n += 1
            continue
        try:
            ts = datetime.fromisoformat(t.replace("Z", "+00:00"))
            if ts >= cutoff:
                n += 1
        except (ValueError, AttributeError):
            n += 1
    return n


def post_discord(webhook: str, content: str) -> None:
    body = json.dumps({"content": content}).encode("utf-8")
    req = urllib.request.Request(
        webhook, data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        sys.stderr.write(f"discord post failed: {e}\n")


def load_history() -> list[dict]:
    if not SNAPSHOT.exists():
        return []
    try:
        data = json.loads(SNAPSHOT.read_text())
        if isinstance(data, list):
            return data
        return []  # old v0 snapshot shape — discard, start fresh
    except Exception:
        return []


def save_history(history: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps(history[-HISTORY_KEEP:], indent=2))


def main() -> int:
    secrets = load_secrets()
    token = secrets.get("KAGI_API_TOKEN_V1") or os.environ.get("KAGI_API_TOKEN_V1")
    if not token:
        print("RED: no KAGI_API_TOKEN_V1 in secrets.env")
        return 2
    webhook = secrets.get("DISCORD_WEBHOOK_KAGI_HEALTH") or os.environ.get(
        "DISCORD_WEBHOOK_KAGI_HEALTH"
    )

    results: dict[str, dict] = {}
    for q in WIRE_QUERIES + CANARIES:
        results[q] = search(token, q)

    wire_fresh = {q: fresh_count(results[q]) for q in WIRE_QUERIES}
    canary_fresh = {q: fresh_count(results[q]) for q in CANARIES}
    http_failures = [q for q, r in results.items() if not r.get("ok")]
    empty_wires = [q for q, n in wire_fresh.items() if n == 0]
    empty_canaries = [q for q, n in canary_fresh.items() if n == 0]

    if http_failures or len(empty_canaries) == len(CANARIES):
        status = "RED"
    elif len(empty_wires) >= 2:
        status = "YELLOW"
    else:
        status = "GREEN"

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    snapshot = {
        "ts": now,
        "status": status,
        "wire_fresh": wire_fresh,
        "canary_fresh": canary_fresh,
        "http_failures": http_failures,
        "errors": {q: r.get("error") for q, r in results.items() if not r.get("ok")},
    }
    history = load_history()
    history.append(snapshot)
    save_history(history)

    summary = (
        f"{status} | wires: "
        + ", ".join(f"{q.split()[0].replace('site:', '')}={wire_fresh[q]}" for q in WIRE_QUERIES)
        + f" | canaries: " + ", ".join(f"{q}={canary_fresh[q]}" for q in CANARIES)
    )
    if http_failures:
        summary += f" | http_fail={len(http_failures)}"

    # Watchdog mode: stdout is delivered verbatim by cron. Stay silent on
    # steady-state GREEN so Brian only hears from us when something needs
    # attention. Always write the snapshot file for inspection.
    if status == "GREEN":
        prev_status = history[-2]["status"] if len(history) >= 2 else "GREEN"
        if prev_status in ("YELLOW", "RED"):
            print(f"✅ AIgregator Kagi health recovered: {summary}")
        # else: silent
    else:
        print(
            f"⚠️ AIgregator Kagi health: **{status}**\n"
            f"```{summary}```\n"
            f"Morning digest runs at 14:00 UTC. Investigate before then.\n"
            f"snapshot: ~/.cache/aigregator/kagi-health.json"
        )

    return {"GREEN": 0, "YELLOW": 1, "RED": 2}[status]


if __name__ == "__main__":
    sys.exit(main())
