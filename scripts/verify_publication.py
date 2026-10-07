#!/usr/bin/env python3
"""Compare the published daily surfaces to the validated local build."""
from __future__ import annotations

import argparse
import hashlib
import sys
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MAX_BODY_BYTES = 10 * 1024 * 1024


def _edition(value: str) -> str:
    if len(value) != 10 or value[4:5] != "-" or value[7:8] != "-":
        raise argparse.ArgumentTypeError("date must be exactly YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise argparse.ArgumentTypeError("date must be exactly YYYY-MM-DD")
    return value


def surfaces(docs: Path, edition: str, origin: str):
    return (
        ("/", docs / "index.html"),
        (f"/digests/{edition}.html", docs / "digests" / f"{edition}.html"),
        ("/feed.xml", docs / "feed.xml"),
        ("/atom.xml", docs / "atom.xml"),
        ("/archive.json", docs / "archive.json"),
    )


def _fetch(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "AIgregator-publication-verifier/1"})
    with urlopen(request, timeout=timeout) as response:
        if response.status != 200:
            raise ValueError(f"HTTP {response.status}")
        body = response.read(MAX_BODY_BYTES + 1)
    if len(body) > MAX_BODY_BYTES:
        raise ValueError(f"response exceeds {MAX_BODY_BYTES} bytes")
    return body


def verify(docs: Path, edition: str, *, timeout: float = 10, retries: int = 6, delay: float = 15):
    """Return comparison rows and failures for all required public surfaces."""
    edition = _edition(edition)
    from build import SITE_URL

    origin = SITE_URL.rstrip("/")
    rows, failures = [], []
    for route, local_path in surfaces(docs, edition, origin):
        url = origin + route
        try:
            expected = local_path.read_bytes()
        except OSError as exc:
            failures.append(f"{url}: cannot read local artifact: {exc}")
            continue
        if not expected:
            failures.append(f"{url}: local artifact is empty")
            continue
        actual, last_error = b"", None
        expected_hash = hashlib.sha256(expected).hexdigest()
        for attempt in range(retries):
            try:
                actual = _fetch(url, timeout)
                actual_hash = hashlib.sha256(actual).hexdigest()
                if actual == expected:
                    last_error = None
                    break
                last_error = ValueError(f"published bytes differ (local {expected_hash}, live {actual_hash})")
            except (HTTPError, URLError, OSError, ValueError) as exc:
                last_error = exc
            if attempt + 1 < retries:
                time.sleep(delay)
        if actual:
            rows.append((url, len(actual), expected_hash, hashlib.sha256(actual).hexdigest(), actual == expected))
        if last_error is not None:
            failures.append(f"{url}: {last_error}")
    return rows, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify public artifacts match the validated local docs.")
    parser.add_argument("--date", required=True, type=_edition)
    parser.add_argument("--docs", required=True, type=Path)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--retries", type=int, default=6)
    parser.add_argument("--delay", type=float, default=15)
    args = parser.parse_args()
    if args.timeout <= 0 or args.retries < 1 or args.delay < 0:
        parser.error("--timeout must be positive, --retries at least 1, and --delay nonnegative")
    rows, failures = verify(args.docs, args.date, timeout=args.timeout, retries=args.retries, delay=args.delay)
    for url, count, expected_hash, actual_hash, matched in rows:
        print(f"{url} bytes={count} local={expected_hash} live={actual_hash}")
    print(f"verified {sum(row[4] for row in rows)}/5 public surfaces (compared {len(rows)}/5)")
    for failure in failures:
        print(f"ERROR: {failure}", file=sys.stderr)
    return 1 if failures or len(rows) != 5 else 0


if __name__ == "__main__":
    sys.exit(main())
