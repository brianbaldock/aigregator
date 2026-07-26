#!/usr/bin/env python3
"""Re-check lychee HTTP/2 protocol errors over HTTP/1.1.

lychee (via reqwest) has no way to force HTTP/1.1, so some live sites fail
with a stream-level "HTTP/2 protocol error" even though they serve fine to a
browser or curl. See https://github.com/lycheeverse/lychee/issues/2264.

Blanket-excluding those domains in lychee.toml stops the false positive but
also stops us catching genuine 404s on them. Instead: let lychee run normally,
then take ONLY the errors whose failure text looks like h2 negotiation and
retry those URLs with curl --http1.1.

  - Every h2-flagged URL recovers over HTTP/1.1 -> exit 0 (false positive)
  - Any URL still fails, or a non-h2 error exists -> exit 1 (real breakage)

Reads lychee's --format json report. Usage:
    verify_h2_failures.py <report.json>
"""

from __future__ import annotations

import json
import subprocess
import sys
import time

# Substrings that identify a failure as HTTP/2 negotiation rather than a real
# dead link. Matched case-insensitively against lychee's status text.
H2_MARKERS = (
    "http/2 protocol error",
    "http2 error",
    "stream error",
)

# When the same URL appears in more than one source file, lychee reports the
# first occurrence with the real error text and later ones as "Error (cached)".
# Those carry no diagnostic text, so they are classified by looking at the
# other occurrences of the same URL rather than on their own.
CACHED_MARKER = "(cached)"

# HTTP statuses we treat as reachable. Mirrors the accept list in lychee.toml:
# 401/403/429 are anti-bot walls, not link rot.
OK_STATUSES = {200, 206, 301, 302, 303, 307, 308, 401, 403, 429}

CURL_TIMEOUT = 20
CURL_ATTEMPTS = 2

# A real browser UA, not a custom identifying one. NPR (and likely other
# bot-mitigated sites) tarpits the "AIgregator-LinkCheck" UA used in
# lychee.toml: the request hangs until timeout rather than being refused,
# which would make this verifier report a live URL as dead. Verified
# 2026-07-26: same URL returns 200 with a Chrome UA or curl's default, and
# times out with the custom one.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)


def is_h2_error(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in H2_MARKERS)


def collect_errors(report: dict) -> list[tuple[str, str]]:
    """Flatten lychee's error_map into (url, status_text) pairs."""
    found: list[tuple[str, str]] = []
    for entries in (report.get("error_map") or {}).values():
        for entry in entries:
            url = entry.get("url")
            if not url:
                continue
            status = entry.get("status") or {}
            text = status.get("text") or ""
            found.append((url, text))
    return found


def check_http11(url: str) -> tuple[bool, str]:
    """Fetch url over HTTP/1.1, retrying once. Returns (reachable, detail)."""
    detail = "not attempted"
    for attempt in range(1, CURL_ATTEMPTS + 1):
        reachable, detail = _curl_once(url)
        if reachable:
            return True, detail
        if attempt < CURL_ATTEMPTS:
            time.sleep(3)
    return False, detail


def _curl_once(url: str) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [
                "curl",
                "--http1.1",
                "--silent",
                "--show-error",
                "--location",
                "--max-time",
                str(CURL_TIMEOUT),
                "--user-agent",
                USER_AGENT,
                "--output",
                "/dev/null",
                "--write-out",
                "%{http_code}",
                url,
            ],
            capture_output=True,
            text=True,
            timeout=CURL_TIMEOUT + 10,
        )
    except subprocess.TimeoutExpired:
        return False, "curl timed out"

    if result.returncode != 0:
        detail = (result.stderr or "").strip() or f"curl exit {result.returncode}"
        return False, detail

    code_text = (result.stdout or "").strip()
    try:
        code = int(code_text)
    except ValueError:
        return False, f"unparseable status {code_text!r}"

    return code in OK_STATUSES, f"HTTP {code}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(f"usage: {argv[0]} <report.json>", file=sys.stderr)
        return 2

    try:
        with open(argv[1], encoding="utf-8") as handle:
            report = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        # Fail closed: if we cannot read the report we cannot clear anything.
        print(f"Cannot read lychee report {argv[1]}: {exc}", file=sys.stderr)
        return 1

    errors = collect_errors(report)
    if not errors:
        print("No errors in lychee report; nothing to re-check.")
        return 0

    # Classify per URL, not per occurrence. A URL is treated as an h2 failure
    # if ANY of its occurrences carries h2 error text; bare "Error (cached)"
    # duplicates inherit that verdict instead of being mistaken for real
    # breakage. A cached entry for a URL with no h2 evidence stays a failure.
    h2_urls = {url for url, text in errors if is_h2_error(text)}

    other_errors = [
        (url, text)
        for url, text in errors
        if url not in h2_urls
        and not (CACHED_MARKER in text.lower() and url in h2_urls)
    ]

    h2_error_urls = list(dict.fromkeys(url for url, _ in errors if url in h2_urls))

    if other_errors:
        print(f"{len(other_errors)} error(s) unrelated to HTTP/2 - these are real:")
        for url, text in other_errors:
            print(f"  FAIL  {url}\n        {text}")

    recovered: list[str] = []
    still_failing: list[tuple[str, str]] = []

    if h2_error_urls:
        print(f"\nRe-checking {len(h2_error_urls)} HTTP/2 error(s) over HTTP/1.1:")
        for url in h2_error_urls:
            reachable, detail = check_http11(url)
            if reachable:
                print(f"  OK    {url} ({detail} over HTTP/1.1)")
                recovered.append(url)
            else:
                print(f"  FAIL  {url} ({detail} over HTTP/1.1)")
                still_failing.append((url, detail))

    print()
    if other_errors or still_failing:
        print(
            f"Link check FAILED: {len(other_errors)} non-HTTP/2 error(s), "
            f"{len(still_failing)} link(s) unreachable over HTTP/1.1."
        )
        return 1

    print(
        f"Link check PASSED: all {len(recovered)} HTTP/2 failure(s) recovered "
        "over HTTP/1.1 (lycheeverse/lychee#2264)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
