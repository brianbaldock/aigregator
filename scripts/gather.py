#!/usr/bin/env python3
"""gather.py — AIgregator source-gather orchestrator.

Replaces the ~200 lines of inline Phase-1 fetcher recipes in the cron prompt.
The cron now calls this once; it runs every source fetcher as an isolated
subprocess and writes all the per-source JSON that merge_score.py consumes.

DESIGN (informed by a gpt-5.6-terra rubber-duck review, 2026-07-22):
  * Per-run isolation: a fresh mkdtemp run dir (AIG_RUN_DIR) so concurrent /
    sibling runs never race on shared files or read each other's stale data.
    --print-run-dir emits the path so the cron threads it into every
    downstream script (merge/curate/render).
  * Process isolation: each fetcher runs as its own subprocess in its own
    process GROUP (start_new_session=True). On a 90s per-source timeout we
    kill the whole group (SIGTERM -> 3s grace -> SIGKILL) and reap it, so a
    hung curl/child can't orphan or zombie.
  * Atomic outputs: fetchers write <file>.tmp then os.rename, so a fetcher
    SIGKILL'd mid-write leaves NO output rather than a truncated JSON that
    merge_score would choke on. Missing output => recorded as a failure in the
    manifest, never a silent empty.
  * Honest status: writes gather_manifest.json (source -> status/count/secs)
    so an outage is distinguishable from a genuinely quiet source, and run
    health is legible at a glance.
  * Global deadline backstop (~150s) so a pathological case can't stall the run.

  NOT sandboxed (no cgroup/seccomp/sandbox user): these fetchers are our own
  committed code hitting known APIs on a trusted single-user box. If they ever
  run untrusted input, add process confinement here.

USAGE:
  python scripts/gather.py --print-run-dir      # mkdtemp, print path, exit
  AIG_RUN_DIR=<dir> python scripts/gather.py     # gather into that dir
  python scripts/gather.py                       # mkdtemp + gather (prints dir first line)
"""
from __future__ import annotations
import argparse
import json
import os
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
FETCHERS = os.path.join(HERE, "fetchers")
REPO = os.path.dirname(HERE)

PER_SOURCE_TIMEOUT = 90     # hard kill ceiling per fetcher
GLOBAL_DEADLINE = 150       # backstop: whole gather must finish within this

# name -> (script path, extra env). opensource uses the committed top-level
# script and its AIG_OPENSOURCE_OUT env; the rest live under fetchers/.
def _sources(run_dir: str):
    return [
        ("rss", [sys.executable, os.path.join(FETCHERS, "rss.py")], {}),
        ("arxiv", [sys.executable, os.path.join(FETCHERS, "arxiv.py")], {}),
        ("reddit", [sys.executable, os.path.join(FETCHERS, "reddit.py")], {}),
        ("bsky", [sys.executable, os.path.join(FETCHERS, "bsky.py")], {}),
        ("hn", [sys.executable, os.path.join(FETCHERS, "hn.py")], {}),
        ("kagi", [sys.executable, os.path.join(FETCHERS, "kagi.py")], {}),
        ("polymarket", [sys.executable, os.path.join(FETCHERS, "polymarket.py")], {}),
        ("opensource",
         [sys.executable, os.path.join(REPO, "scripts", "fetch_opensource.py")],
         {"AIG_OPENSOURCE_OUT": os.path.join(run_dir, "opensource.json")}),
    ]

# expected output file per source (for the manifest count / presence check)
OUTPUT_FILE = {
    "rss": "rss_items.json", "arxiv": "arxiv_items.json",
    "reddit": "reddit_items.json", "bsky": "bsky_items.json",
    "hn": "hn_items.json", "polymarket": "polymarket.json",
    "opensource": "opensource.json",
}


def _run_dir_for_today() -> str:
    """Date-scoped run dir: /tmp/aig/run-<UTC-date>/. Idempotent — a same-day
    re-run reuses the day's dir (and its already-gathered files + curation
    fragments), which is exactly the idempotent-recovery behavior the curate
    phase wants. The UTC date is the session key; no random suffix, no mutable
    'latest' pointer to race on."""
    from datetime import datetime, timezone
    base = "/tmp/aig"
    os.makedirs(base, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    d = os.path.join(base, f"run-{day}")
    os.makedirs(d, exist_ok=True)
    return d


def _write_pointer(run_dir: str) -> None:
    """Best-effort global pointer for debugging/observability. NOT used for
    resolution (that's date-derived) so it cannot introduce a cross-run race."""
    try:
        ptr = os.path.join(REPO, ".last_run_dir")
        with open(ptr, "w") as f:
            f.write(run_dir + "\n")
    except Exception:
        pass


def _count(path: str) -> int | None:
    try:
        d = json.load(open(path))
    except Exception:
        return None
    if isinstance(d, list):
        return len(d)
    if isinstance(d, dict):
        # opensource.json has buckets; sum list-valued values
        return sum(len(v) for v in d.values() if isinstance(v, list)) or len(d)
    return None


def _launch(cmd, env):
    full_env = dict(os.environ)
    full_env.update(env)
    return subprocess.Popen(
        cmd, env=full_env, cwd=REPO,
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
        start_new_session=True,  # own process group => group-kill on timeout
    )


def _kill_group(proc):
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGTERM)
    except Exception:
        pass
    try:
        proc.wait(timeout=3)
        return
    except Exception:
        pass
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        pass
    try:
        proc.wait(timeout=3)
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--print-run-dir", action="store_true",
                    help="Print today's date-scoped run dir (creating it if "
                         "needed), then exit. Idempotent: same UTC day = same dir.")
    args = ap.parse_args()

    if args.print_run_dir:
        d = _run_dir_for_today()
        _write_pointer(d)
        print(d)
        return

    run_dir = os.environ.get("AIG_RUN_DIR") or _run_dir_for_today()
    os.environ["AIG_RUN_DIR"] = run_dir
    _write_pointer(run_dir)
    # First stdout line is always the run dir so callers can capture it.
    print(run_dir, flush=True)

    sources = _sources(run_dir)
    # launch all concurrently, each in its own process group
    procs = {}
    starts = {}
    for name, cmd, env in sources:
        procs[name] = _launch(cmd, env)
        starts[name] = time.time()

    manifest = {}
    gather_start = time.time()
    pending = set(procs)
    while pending:
        if time.time() - gather_start > GLOBAL_DEADLINE:
            for name in list(pending):
                _kill_group(procs[name])
                manifest[name] = {"status": "GLOBAL_DEADLINE",
                                  "secs": round(time.time() - starts[name], 1)}
            break
        for name in list(pending):
            p = procs[name]
            elapsed = time.time() - starts[name]
            rc = p.poll()
            if rc is not None:
                secs = round(elapsed, 1)
                fn = OUTPUT_FILE.get(name)
                if name == "kagi":
                    kdir = os.path.join(run_dir, "kagi")
                    n = len([f for f in os.listdir(kdir)
                             if f.endswith(".json")]) if os.path.isdir(kdir) else 0
                    manifest[name] = {"status": "OK" if n else "EMPTY",
                                      "queries_landed": n, "secs": secs, "rc": rc}
                elif fn is None:
                    manifest[name] = {"status": "FAIL", "count": None,
                                      "secs": secs, "rc": rc,
                                      "err": "no OUTPUT_FILE mapping"}
                else:
                    path = os.path.join(run_dir, fn)
                    cnt = _count(path) if os.path.exists(path) else None
                    if cnt is None:
                        manifest[name] = {"status": "FAIL", "count": None,
                                          "secs": secs, "rc": rc,
                                          "err": (p.stderr.read().decode()[-160:]
                                                  if p.stderr else "")}
                    else:
                        manifest[name] = {"status": "OK", "count": cnt, "secs": secs}
                pending.discard(name)
            elif elapsed > PER_SOURCE_TIMEOUT:
                _kill_group(p)
                manifest[name] = {"status": "TIMEOUT", "secs": round(elapsed, 1)}
                pending.discard(name)
        if pending:
            time.sleep(0.5)

    # write manifest atomically
    mtmp = os.path.join(run_dir, "gather_manifest.json.tmp")
    with open(mtmp, "w") as f:
        json.dump(manifest, f, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.rename(mtmp, os.path.join(run_dir, "gather_manifest.json"))

    # human-readable summary to stderr
    print("\n=== gather summary ===", file=sys.stderr)
    for name, _c, _e in sources:
        m = manifest.get(name, {"status": "MISSING"})
        detail = m.get("count", m.get("queries_landed", ""))
        print(f"  {name:12} {m['status']:16} {detail}  ({m.get('secs','?')}s)",
              file=sys.stderr)
    ok = sum(1 for m in manifest.values() if m["status"] == "OK")
    print(f"=== {ok}/{len(sources)} sources OK, run_dir={run_dir} ===", file=sys.stderr)


if __name__ == "__main__":
    main()
