#!/usr/bin/env python3
"""Collect source artifacts into a date-scoped run directory safely."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
FETCHERS = os.path.join(HERE, "fetchers")
REPO = os.path.dirname(HERE)
PER_SOURCE_TIMEOUT = 90
GLOBAL_DEADLINE = 150

OUTPUT_FILE = {
    "rss": "rss_items.json", "arxiv": "arxiv_items.json",
    "reddit": "reddit_items.json", "bsky": "bsky_items.json",
    "hn": "hn_items.json", "polymarket": "polymarket.json",
    "opensource": "opensource.json",
}
OPENSOURCE_BUCKETS = {"github_trending", "github_watchlist", "hf_trending"}


def _sources(run_dir: str):
    return [
        ("rss", [sys.executable, os.path.join(FETCHERS, "rss.py")], {}),
        ("arxiv", [sys.executable, os.path.join(FETCHERS, "arxiv.py")], {}),
        ("reddit", [sys.executable, os.path.join(FETCHERS, "reddit.py")], {}),
        ("bsky", [sys.executable, os.path.join(FETCHERS, "bsky.py")], {}),
        ("hn", [sys.executable, os.path.join(FETCHERS, "hn.py")], {}),
        ("kagi", [sys.executable, os.path.join(FETCHERS, "kagi.py")], {}),
        ("polymarket", [sys.executable, os.path.join(FETCHERS, "polymarket.py")], {}),
        ("opensource", [sys.executable, os.path.join(REPO, "scripts", "fetch_opensource.py")],
         {"AIG_OPENSOURCE_OUT": os.path.join(run_dir, "opensource.json")}),
    ]


def _run_dir_for_today() -> str:
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = os.path.join("/tmp/aig", f"run-{day}")
    os.makedirs(path, exist_ok=True)
    return path


def _write_pointer(run_dir: str) -> None:
    try:
        with open(os.path.join(REPO, ".last_run_dir"), "w") as fh:
            fh.write(run_dir + "\n")
    except OSError:
        pass


def _launch(cmd, env):
    full_env = dict(os.environ)
    full_env.update(env)
    proc = subprocess.Popen(
        cmd, env=full_env, cwd=REPO, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, start_new_session=True,
    )
    proc._aig_pgid = proc.pid
    return proc


def _kill_group(proc):
    pgid = getattr(proc, "_aig_pgid", proc.pid)
    try:
        os.killpg(pgid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        time.sleep(0.05)
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        pass


def _read_json(path: str):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def _records(value) -> int | None:
    return len(value) if isinstance(value, list) and all(isinstance(item, dict) for item in value) else None


def _validate(name: str, stage: str):
    """Return (record count, staged relative paths) or (None, reason)."""
    if name == "kagi":
        directory = os.path.join(stage, "kagi")
        paths = sorted(
            os.path.join(directory, entry) for entry in os.listdir(directory)
            if entry.endswith(".json")
        ) if os.path.isdir(directory) else []
        count = 0
        for path in paths:
            payload = _read_json(path)
            data = payload.get("data") if isinstance(payload, dict) else None
            search = data.get("search") if isinstance(data, dict) else None
            records = _records(search)
            if records is None:
                return None, "invalid kagi schema"
            count += records
        return count, [os.path.relpath(path, stage) for path in paths]
    filename = OUTPUT_FILE.get(name)
    if filename is None:
        return None, "no output mapping"
    payload = _read_json(os.path.join(stage, filename))
    if name == "opensource":
        if not isinstance(payload, dict) or set(payload) != OPENSOURCE_BUCKETS:
            return None, "invalid opensource schema"
        counts = [_records(payload[bucket]) for bucket in OPENSOURCE_BUCKETS]
        if any(count is None for count in counts):
            return None, "invalid opensource schema"
        return sum(counts), [filename]
    count = _records(payload)
    return (count, [filename]) if count is not None else (None, "invalid source schema")


def _remove_consumed_output(run_dir: str, name: str) -> None:
    if name == "kagi":
        directory = os.path.join(run_dir, "kagi")
        if os.path.isdir(directory):
            for entry in os.listdir(directory):
                if entry.endswith(".json"):
                    os.unlink(os.path.join(directory, entry))
        return
    filename = OUTPUT_FILE.get(name)
    if filename:
        try:
            os.unlink(os.path.join(run_dir, filename))
        except FileNotFoundError:
            pass


def _promote(run_dir: str, stage: str, name: str, paths: list[str]):
    _remove_consumed_output(run_dir, name)
    output_paths = []
    for relative in paths:
        source = os.path.join(stage, relative)
        destination = os.path.join(run_dir, relative)
        os.makedirs(os.path.dirname(destination), exist_ok=True)
        os.replace(source, destination)
        with open(destination, "rb") as fh:
            output_paths.append({"path": relative, "sha256": hashlib.sha256(fh.read()).hexdigest()})
    return output_paths


def _entry(status, secs, generation_id, collected_at, **extra):
    return {
        "status": status, "secs": secs, "generation_id": generation_id,
        "collected_at": collected_at, "rc": None, "count": None,
        "outputs": [], **extra,
    }


def _write_manifest(run_dir: str, manifest: dict) -> None:
    temporary = os.path.join(run_dir, "gather_manifest.json.tmp")
    with open(temporary, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(temporary, os.path.join(run_dir, "gather_manifest.json"))


def _fail_orchestration(run_dir, sources, procs, manifest, generation_id, collected_at, reason):
    for proc in procs.values():
        _kill_group(proc)
    for name, _, _ in sources:
        _remove_consumed_output(run_dir, name)
        proc = procs.get(name)
        rc = proc.poll() if proc else None
        manifest[name] = _entry(
            "FAIL", 0, generation_id, collected_at, rc=rc,
            err=f"orchestration failure: {reason}",
        )
    _write_manifest(run_dir, manifest)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--print-run-dir", action="store_true")
    args = parser.parse_args()
    if args.print_run_dir:
        path = _run_dir_for_today()
        _write_pointer(path)
        print(path)
        return 0

    run_dir = os.environ.get("AIG_RUN_DIR") or _run_dir_for_today()
    os.makedirs(run_dir, exist_ok=True)
    lock_path = os.path.join(run_dir, ".gather.lock")
    lock = open(lock_path, "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print(f"gather lock busy: {run_dir}", file=sys.stderr)
        lock.close()
        return 1

    generation_id = uuid.uuid4().hex
    collected_at = datetime.now(timezone.utc).isoformat()
    stage = tempfile.mkdtemp(prefix=".gather-", dir=run_dir)
    procs = {}
    try:
        _write_pointer(run_dir)
        print(run_dir, flush=True)
        sources = _sources(stage)
        manifest = {
            name: _entry("IN_PROGRESS", 0, generation_id, collected_at, reason="collection in progress")
            for name, _, _ in sources
        }
        _write_manifest(run_dir, manifest)
        starts = {}
        try:
            for name, cmd, extra_env in sources:
                env = {"AIG_RUN_DIR": stage, **extra_env}
                procs[name] = _launch(cmd, env)
                starts[name] = time.monotonic()
        except OSError as exc:
            _fail_orchestration(run_dir, sources, procs, manifest, generation_id, collected_at,
                                "source launch failed")
            return 1

        pending = set(procs)
        gather_start = time.monotonic()
        while pending:
            if time.monotonic() - gather_start > GLOBAL_DEADLINE:
                for name in list(pending):
                    _kill_group(procs[name])
                    _remove_consumed_output(run_dir, name)
                    manifest[name] = _entry("GLOBAL_DEADLINE", round(time.monotonic() - starts[name], 1),
                                            generation_id, collected_at, reason="global deadline exceeded")
                    pending.remove(name)
                break
            for name in list(pending):
                proc = procs[name]
                elapsed = time.monotonic() - starts[name]
                rc = proc.poll()
                if rc is None and elapsed <= PER_SOURCE_TIMEOUT:
                    continue
                secs = round(elapsed, 1)
                if rc is None:
                    _kill_group(proc)
                    _remove_consumed_output(run_dir, name)
                    manifest[name] = _entry("TIMEOUT", secs, generation_id, collected_at,
                                            reason="per-source timeout")
                elif rc != 0:
                    _remove_consumed_output(run_dir, name)
                    manifest[name] = _entry("FAIL", secs, generation_id, collected_at,
                                            rc=rc, err="fetcher exited unsuccessfully")
                else:
                    count, paths_or_reason = _validate(name, stage)
                    if count is None:
                        _remove_consumed_output(run_dir, name)
                        manifest[name] = _entry("FAIL", secs, generation_id, collected_at,
                                                rc=rc, err=paths_or_reason)
                    else:
                        try:
                            outputs = _promote(run_dir, stage, name, paths_or_reason)
                        except OSError:
                            _fail_orchestration(
                                run_dir, sources, procs, manifest, generation_id, collected_at,
                                "output promotion failed",
                            )
                            return 1
                        status = "OK" if count else "EMPTY"
                        extra = {"rc": rc, "count": count, "outputs": outputs}
                        if status == "EMPTY":
                            extra["reason"] = "source completed with zero records"
                        if name == "kagi":
                            extra["queries_landed"] = len(paths_or_reason)
                        manifest[name] = _entry(status, secs, generation_id, collected_at, **extra)
                pending.remove(name)
            if pending:
                time.sleep(0.05)

        _write_manifest(run_dir, manifest)
        ok = sum(entry["status"] == "OK" for entry in manifest.values())
        for name, _, _ in sources:
            entry = manifest[name]
            print(f"  {name:12} {entry['status']:16} {entry.get('count', '')}",
                  file=sys.stderr)
        return 0 if ok else 1
    finally:
        shutil.rmtree(stage, ignore_errors=True)
        lock.close()


if __name__ == "__main__":
    sys.exit(main())
