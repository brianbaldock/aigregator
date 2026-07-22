#!/usr/bin/env python3
"""kagi.py (fetcher) — run the wire-service + topic Kagi searches into
$RUN_DIR/kagi/*.json, which merge_score globs. Wraps the committed
scripts/kagi.py search CLI (which prints JSON to stdout). NOT the same file as
scripts/kagi.py — this is the AIgregator-specific batch of queries.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import run_dir, log  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KAGI = os.path.join(REPO, "scripts", "kagi.py")

# (output-name, query, days)
QUERIES = [
    ("reuters", "site:reuters.com AI", 2),
    ("apnews", "site:apnews.com AI", 2),
    ("bloomberg", "site:bloomberg.com AI", 2),
    ("wsj", "site:wsj.com AI", 2),
    ("labs", "Anthropic announcement OR OpenAI launches OR Google DeepMind release", 3),
    ("funding", "AI funding OR AI startup raises", 3),
    ("oss", "open source LLM OR open weights", 3),
    ("policy", "AI policy site:reuters.com OR site:apnews.com OR site:bloomberg.com", 3),
]


def main():
    kdir = os.path.join(run_dir(), "kagi")
    os.makedirs(kdir, exist_ok=True)
    landed = 0
    for name, query, days in QUERIES:
        out = os.path.join(kdir, f"{name}.json")
        tmp = out + ".tmp"
        try:
            with open(tmp, "w") as fh:
                r = subprocess.run(
                    [sys.executable, KAGI, "search", query,
                     "--limit", "10", "--days", str(days)],
                    stdout=fh, stderr=subprocess.PIPE, timeout=25, cwd=REPO)
            if r.returncode == 0 and os.path.getsize(tmp) > 2:
                os.rename(tmp, out)  # atomic; only publish a complete file
                landed += 1
                log(f"{name}: ok")
            else:
                os.path.exists(tmp) and os.remove(tmp)
                log(f"{name}: FAIL rc={r.returncode} {r.stderr.decode()[:60]}")
        except Exception as e:
            os.path.exists(tmp) and os.remove(tmp)
            log(f"{name}: FAIL {str(e)[:60]}")
    log(f"{landed}/{len(QUERIES)} kagi queries landed")


if __name__ == "__main__":
    main()
