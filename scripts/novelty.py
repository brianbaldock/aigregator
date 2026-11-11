"""Novelty gate for repo/model discovery (Open Source + Cool Projects).

A GitHub repo or HuggingFace model that we already cited in any of the last
NOVELTY_DAYS daily digests is not news again just because it is still popular.
Before this gate, the same handful (hermes-agent, Qwen, openclaw) filled the
Open Source section for three straight weeks.

Exception: an item carrying a fresh release (os_kind == "release") is allowed
through, because a new version is new information.
"""
from __future__ import annotations

import os
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

NOVELTY_DAYS = 14
DEFAULT_DIGESTS = Path(__file__).resolve().parents[1] / "digests"

_GH = re.compile(r"https?://(?:www\.)?github\.com/([A-Za-z0-9][A-Za-z0-9_.-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*)")
_HF = re.compile(r"https?://(?:www\.)?huggingface\.co/(?!blog/|datasets/|spaces/|papers/|docs/)"
                 r"([A-Za-z0-9][A-Za-z0-9_.-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*)")
_HF_DS = re.compile(r"https?://(?:www\.)?huggingface\.co/datasets/([A-Za-z0-9][A-Za-z0-9_.-]*)/([A-Za-z0-9][A-Za-z0-9_.-]*)")


def identity(url: str) -> str | None:
    """Stable lowercase key for a repo/model URL, or None if not one."""
    if not isinstance(url, str):
        return None
    m = _GH.match(url)
    if m:
        return f"gh:{m.group(1)}/{m.group(2).removesuffix('.git')}".lower()
    m = _HF_DS.match(url)
    if m:
        return f"hfds:{m.group(1)}/{m.group(2)}".lower()
    m = _HF.match(url)
    if m:
        return f"hf:{m.group(1)}/{m.group(2)}".lower()
    return None


def recent_identities(today: date | None = None, digests_dir: Path | str | None = None,
                      days: int = NOVELTY_DAYS) -> set[str]:
    """Identities cited in digests dated in [today - days, today), excluding today.

    Today's own file is excluded so a same-day re-render does not reject the
    items it is about to publish.
    """
    today = today or datetime.now(timezone.utc).date()
    root = Path(digests_dir or os.environ.get("AIG_DIGESTS_DIR") or DEFAULT_DIGESTS)
    seen: set[str] = set()
    for offset in range(1, days + 1):
        fp = root / f"{(today - timedelta(days=offset)).isoformat()}.md"
        try:
            text = fp.read_text(encoding="utf-8")
        except OSError:
            continue
        for url in re.findall(r"\]\((https?://[^)\s]+)\)", text):
            key = identity(url)
            if key:
                seen.add(key)
    return seen


RELEASE_COOLDOWN_DAYS = 7


def filter_novel(items: list[dict], seen: set[str], log=None,
                 seen_recent_week: set[str] | None = None) -> list[dict]:
    """Drop items whose repo/model was cited recently.

    Releases bypass the 14-day gate (a new version is new information) but not
    a 7-day cooldown: orgs that tag releases near-daily (openclaw) would
    otherwise reappear every morning anyway.
    """
    week = seen_recent_week or set()
    kept = []
    for it in items:
        key = identity(it.get("url", ""))
        if key and it.get("os_kind") == "release":
            if key in week:
                if log:
                    log(f"novelty: skip release {key} (cited in last {RELEASE_COOLDOWN_DAYS} days)")
                continue
        elif key and key in seen:
            if log:
                log(f"novelty: skip {key} (cited in last {NOVELTY_DAYS} days)")
            continue
        kept.append(it)
    return kept
