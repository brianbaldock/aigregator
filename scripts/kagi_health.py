#!/usr/bin/env python3
"""
Kagi Enrich API healthcheck.

Probes the 6 Phase 1C queries plus 2 always-on canaries against both
/enrich/news and /enrich/web. Writes a snapshot to
~/.cache/aigregator/kagi-health.json (last 7 retained) and prints a
one-line status summary. Exits 0 (green), 1 (yellow), or 2 (red).

If a Discord webhook is configured at $DISCORD_WEBHOOK_KAGI_HEALTH and
the status transitions (green→yellow, →red, recovery), post a short
alert. Steady-state status changes (green→green) post nothing.

Cost: 16 calls/day worst case. Kagi bills only on non-empty results, so
the practical floor is ~$0.024-0.032/day.

Run unattended ~13:55 UTC (5 min before the digest cron).
"""
from __future__ import annotations

import json
import os
import statistics
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SECRETS = Path.home() / ".config" / "aigregator" / "secrets.env"
CACHE_DIR = Path.home() / ".cache" / "aigregator"
SNAPSHOT = CACHE_DIR / "kagi-health.json"
HISTORY_KEEP = 7
BASE = "https://kagi.com/api/v0"

# Mirrors Phase 1C in jobs.json. Keep in sync if that list changes.
DIGEST_QUERIES = [
    "AI",
    "LLM",
    "open source AI",
    "AI safety",
    "AI policy",
    "AI agents",
]
# Always-on controls. If these go zero, the API itself is broken, not
# our query selection.
CANARIES = ["microsoft", "linux"]

ENDPOINTS = ["/enrich/news", "/enrich/web"]


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


def call(token: str, path: str, query: str) -> dict:
    url = f"{BASE}{path}?{urllib.parse.urlencode({'q': query})}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bot {token}"})
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            body = json.loads(r.read())
        return {"ok": True, "ms": int((time.time() - t0) * 1000), "data": body}
    except Exception as e:
        return {"ok": False, "ms": int((time.time() - t0) * 1000), "error": str(e)}


def parse_published_days(item: dict) -> int | None:
    """Best-effort: return age in days from now for the item's published date."""
    for key in ("published", "date", "pubdate"):
        v = item.get(key)
        if not v:
            continue
        try:
            # Accept ISO 8601 with or without timezone
            s = str(v).replace("Z", "+00:00")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - dt).days
        except Exception:
            continue
    return None


def probe(token: str) -> dict:
    """Run all queries × endpoints and roll up signal metrics."""
    probes = []
    for q in DIGEST_QUERIES + CANARIES:
        for ep in ENDPOINTS:
            r = call(token, ep, q)
            data = r.get("data") if r["ok"] else None
            items = (data or {}).get("data") if isinstance(data, dict) else None
            count = len(items) if isinstance(items, list) else 0
            ages = []
            if isinstance(items, list):
                for it in items:
                    if isinstance(it, dict):
                        a = parse_published_days(it)
                        if a is not None:
                            ages.append(a)
            probes.append({
                "query": q,
                "endpoint": ep,
                "is_canary": q in CANARIES,
                "ok": r["ok"],
                "ms": r["ms"],
                "count": count,
                "median_age_days": int(statistics.median(ages)) if ages else None,
                "error": r.get("error"),
            })
            # Be polite — small inter-call gap
            time.sleep(0.25)
    return {"probes": probes}


def classify(snapshot: dict) -> tuple[str, list[str]]:
    """Return (status, reasons) where status in {green, yellow, red}."""
    probes = snapshot["probes"]
    reasons: list[str] = []

    # RED: any HTTP failure on a canary, or all canaries returning zero results
    canary = [p for p in probes if p["is_canary"]]
    canary_fail = [p for p in canary if not p["ok"]]
    canary_zero = [p for p in canary if p["ok"] and p["count"] == 0]
    if canary_fail:
        reasons.append(f"{len(canary_fail)} canary HTTP failure(s)")
        return "red", reasons
    if canary and len(canary_zero) == len(canary):
        reasons.append("all canaries returned zero results (API likely broken)")
        return "red", reasons

    # RED: every digest query returned zero across both endpoints
    digest = [p for p in probes if not p["is_canary"]]
    digest_zero = [p for p in digest if p["ok"] and p["count"] == 0]
    if digest and len(digest_zero) == len(digest):
        reasons.append("every digest query returned zero results")
        return "red", reasons

    # YELLOW: >50% of digest probes empty
    if digest and (len(digest_zero) / len(digest)) > 0.5:
        reasons.append(f"{len(digest_zero)}/{len(digest)} digest probes empty (>50%)")
        return "yellow", reasons

    # YELLOW: any digest query HTTP failure
    digest_fail = [p for p in digest if not p["ok"]]
    if digest_fail:
        reasons.append(f"{len(digest_fail)} digest query HTTP failure(s)")
        return "yellow", reasons

    # YELLOW: median freshness >30d across all returned items
    all_ages = [p["median_age_days"] for p in probes if p["median_age_days"] is not None]
    if all_ages and statistics.median(all_ages) > 30:
        reasons.append(f"median item age {int(statistics.median(all_ages))}d > 30d")
        return "yellow", reasons

    return "green", reasons or ["all probes nominal"]


def load_history() -> list[dict]:
    if not SNAPSHOT.exists():
        return []
    try:
        return json.loads(SNAPSHOT.read_text()).get("history", [])
    except Exception:
        return []


def save_history(history: list[dict]) -> None:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    SNAPSHOT.write_text(json.dumps({"history": history[-HISTORY_KEEP:]}, indent=2))


def discord_alert(webhook: str, msg: str) -> None:
    payload = json.dumps({"content": msg}).encode()
    req = urllib.request.Request(
        webhook,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        urllib.request.urlopen(req, timeout=10).read()
    except Exception as e:
        print(f"discord post failed: {e}", file=sys.stderr)


def main() -> int:
    secrets = load_secrets()
    token = secrets.get("KAGI_API_TOKEN")
    if not token:
        print("ERR: missing KAGI_API_TOKEN in secrets", file=sys.stderr)
        return 2

    snap = probe(token)
    status, reasons = classify(snap)
    snap["status"] = status
    snap["reasons"] = reasons
    snap["ts"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    history = load_history()
    prev_status = history[-1]["status"] if history else None
    history.append(snap)
    save_history(history)

    # Compact one-liner for cron log
    digest = [p for p in snap["probes"] if not p["is_canary"]]
    canary = [p for p in snap["probes"] if p["is_canary"]]
    d_ok = sum(1 for p in digest if p["ok"] and p["count"] > 0)
    c_ok = sum(1 for p in canary if p["ok"] and p["count"] > 0)
    print(
        f"[kagi-health] {status.upper()} digest {d_ok}/{len(digest)} "
        f"canary {c_ok}/{len(canary)} :: {'; '.join(reasons)}"
    )

    # Alert on transition only (and on any red/yellow with no prior history)
    webhook = secrets.get("DISCORD_WEBHOOK_KAGI_HEALTH") or os.environ.get(
        "DISCORD_WEBHOOK_KAGI_HEALTH"
    )
    if webhook and status != "green" and status != prev_status:
        emoji = {"red": "🔴", "yellow": "🟡", "green": "🟢"}[status]
        discord_alert(
            webhook,
            f"{emoji} Kagi Enrich health: **{status.upper()}** "
            f"(was {prev_status or 'n/a'})\n"
            f"digest {d_ok}/{len(digest)} · canary {c_ok}/{len(canary)}\n"
            f"reasons: {'; '.join(reasons)}",
        )
    elif webhook and status == "green" and prev_status in ("red", "yellow"):
        discord_alert(
            webhook,
            f"🟢 Kagi Enrich recovered (was {prev_status}). "
            f"digest {d_ok}/{len(digest)} · canary {c_ok}/{len(canary)}",
        )

    return {"green": 0, "yellow": 1, "red": 2}[status]


if __name__ == "__main__":
    sys.exit(main())
