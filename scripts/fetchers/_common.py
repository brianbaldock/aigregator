#!/usr/bin/env python3
"""_common.py — shared contract for AIgregator source fetchers.

Every fetcher writes its output via atomic_write_json() so a fetcher killed
mid-write (SIGKILL on timeout) never leaves a truncated/corrupt JSON that
merge_score.py would choke on: we write to <path>.tmp, fsync, then os.rename
(atomic on the same filesystem). A killed fetcher leaves NO output file at all,
which gather.py records as a failure in the manifest rather than a silent empty.

Also centralizes the urllib timeout + UA so socket-level behavior does not drift
across the eight fetchers (Terra rubber-duck review, 2026-07-22).
"""
from __future__ import annotations
import json
import os
import sys
import urllib.request

DEFAULT_UA = "aigregator/1.0 (+https://aigregator.news)"
# connect+read guard INSIDE each fetcher. The 90s subprocess kill in gather.py
# protects the orchestrator; these protect the worker from tying up its slot.
DEFAULT_TIMEOUT = 20


def run_dir() -> str:
    """Directory this fetcher must write into. gather.py sets AIG_RUN_DIR;
    falls back to /tmp/aig for manual/standalone runs."""
    d = os.environ.get("AIG_RUN_DIR", "/tmp/aig")
    os.makedirs(d, exist_ok=True)
    return d


def out_path(name: str) -> str:
    """Absolute path for an output file inside the active run dir."""
    return os.path.join(run_dir(), name)


def atomic_write_json(path: str, data) -> None:
    """Write JSON to path atomically: <path>.tmp -> fsync -> rename."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.flush()
        os.fsync(f.fileno())
    os.rename(tmp, path)


def get(url: str, timeout: int = DEFAULT_TIMEOUT, headers: dict | None = None,
        proxy: str | None = None) -> bytes:
    """GET with a bounded connect/read timeout. Raises on non-2xx/network error."""
    h = {"User-Agent": DEFAULT_UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    if proxy:
        ph = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
        opener = urllib.request.build_opener(ph)
        with opener.open(req, timeout=timeout) as r:
            return r.read()
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def log(msg: str) -> None:
    """One-line stderr log, prefixed with the fetcher's module name."""
    who = os.path.basename(sys.argv[0]).replace(".py", "")
    print(f"[{who}] {msg}", file=sys.stderr)
