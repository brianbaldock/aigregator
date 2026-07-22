#!/usr/bin/env python3
"""run_dir.py — resolve the current AIgregator gather run directory.

Every digest phase calls this instead of the agent carrying a literal path
across turns (shell vars don't survive between tool calls). Resolution order:

  1. $AIG_RUN_DIR if set and it exists  (explicit wins — deterministic when the
     cron threads it through)
  2. today's date-scoped dir /tmp/aig/run-<UTC-date>/ if it exists  (the safety
     net: the agent can always recover the path from the date alone)

Prints the resolved path on success (exit 0). If neither exists, prints an
error to stderr and exits 1 so a phase can't silently operate on the wrong dir.
Warns (stderr, still exit 0) if the dir exists but has no gather_manifest.json,
which means gather hasn't run yet for this dir.

USAGE:
  RUN_DIR=$(python scripts/run_dir.py)      # resolve, or fail loudly
  python scripts/run_dir.py --require-manifest   # exit 1 if no manifest yet
"""
from __future__ import annotations
import argparse
import os
import sys
from datetime import datetime, timezone


def resolve() -> str | None:
    env = os.environ.get("AIG_RUN_DIR")
    if env and os.path.isdir(env):
        return env
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    d = os.path.join("/tmp/aig", f"run-{day}")
    if os.path.isdir(d):
        return d
    return None


def run_dir_default() -> str:
    """Importable default for downstream scripts' argparse defaults.

    Returns the resolved run dir (env override or today's date-scoped dir) if it
    exists, else the date-scoped path (which the caller will create/use). This
    lets merge_score/curate/write_digest default to the CURRENT run dir with NO
    argument and NO shell command-substitution in the cron prompt — the single
    most robust way to thread the run dir through an unattended pipeline.
    """
    d = resolve()
    if d:
        return d
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return os.path.join("/tmp/aig", f"run-{day}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--require-manifest", action="store_true",
                    help="Exit 1 if the run dir has no gather_manifest.json yet.")
    args = ap.parse_args()

    d = resolve()
    if not d:
        print("run_dir: no run dir found (set AIG_RUN_DIR or run gather.py first)",
              file=sys.stderr)
        sys.exit(1)

    manifest = os.path.join(d, "gather_manifest.json")
    if not os.path.exists(manifest):
        msg = f"run_dir: {d} exists but has no gather_manifest.json (gather not run yet?)"
        if args.require_manifest:
            print(msg, file=sys.stderr)
            sys.exit(1)
        print(msg, file=sys.stderr)

    print(d)


if __name__ == "__main__":
    main()
