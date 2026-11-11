"""Novelty gate + project-discovery ordering (Cool Projects / Open Source overhaul).

Regressions guarded:
- the same repos/models (hermes-agent, Qwen, openclaw) filled Open Source for 3 weeks;
- r/BestGitHubRepos was fetched last and lost to Reddit 429s on every run.
"""
import sys
import tempfile
import unittest
import urllib.error
from datetime import date
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "fetchers"))

import novelty  # noqa: E402
import reddit  # noqa: E402

TODAY = date(2026, 11, 10)


def _digest(root, day, urls):
    body = "\n".join(f"- [x]({u}) blurb" for u in urls)
    Path(root, f"{day}.md").write_text(f"# {day}\n\n## 🌱 Open Source & Emerging\n{body}\n")


class NoveltyTests(unittest.TestCase):
    def test_identity_normalizes_github_and_hf(self):
        self.assertEqual(novelty.identity("https://github.com/NousResearch/hermes-agent"),
                         "gh:nousresearch/hermes-agent")
        self.assertEqual(novelty.identity("https://www.github.com/A/B.git"), "gh:a/b")
        self.assertEqual(novelty.identity("https://huggingface.co/Qwen/Qwen3.8-27B"), "hf:qwen/qwen3.8-27b")
        self.assertEqual(novelty.identity("https://huggingface.co/datasets/x/y"), "hfds:x/y")
        self.assertIsNone(novelty.identity("https://huggingface.co/blog/some-post"))
        self.assertIsNone(novelty.identity("https://www.theverge.com/a/b"))

    def test_window_is_previous_14_days_and_excludes_today(self):
        with tempfile.TemporaryDirectory() as d:
            _digest(d, "2026-11-10", ["https://github.com/today/repo"])      # today: excluded
            _digest(d, "2026-11-09", ["https://github.com/yday/repo"])       # 1 day: included
            _digest(d, "2026-10-27", ["https://github.com/edge/repo"])       # 14 days: included
            _digest(d, "2026-10-26", ["https://github.com/old/repo"])        # 15 days: excluded
            seen = novelty.recent_identities(TODAY, d)
        self.assertEqual(seen, {"gh:yday/repo", "gh:edge/repo"})

    def test_filter_drops_repeats_but_keeps_releases_and_new(self):
        seen = {"gh:nousresearch/hermes-agent", "hf:qwen/qwen3.8-27b"}
        items = [
            {"url": "https://github.com/NousResearch/hermes-agent", "os_kind": "watchlist"},
            {"url": "https://github.com/NousResearch/hermes-agent", "os_kind": "release"},
            {"url": "https://huggingface.co/Qwen/Qwen3.8-27B", "os_kind": "hf"},
            {"url": "https://github.com/new/thing", "os_kind": "trending"},
            {"url": "https://www.bbc.co.uk/news/x"},
        ]
        kept = novelty.filter_novel(items, seen, seen_recent_week=set())
        self.assertEqual([(i["url"], i.get("os_kind")) for i in kept], [
            ("https://github.com/NousResearch/hermes-agent", "release"),
            ("https://github.com/new/thing", "trending"),
            ("https://www.bbc.co.uk/news/x", None),
        ])

    def test_release_blocked_inside_7_day_cooldown(self):
        rel = [{"url": "https://github.com/openclaw/openclaw", "os_kind": "release"}]
        week = {"gh:openclaw/openclaw"}
        self.assertEqual(novelty.filter_novel(rel, week, seen_recent_week=week), [])
        self.assertEqual(len(novelty.filter_novel(rel, week, seen_recent_week=set())), 1)

    def test_against_real_archive_hermes_and_qwen_are_blocked(self):
        # The live repeat offenders from Oct/Nov 2026 must be caught by the real digests.
        seen = novelty.recent_identities(TODAY)
        self.assertIn("gh:nousresearch/hermes-agent", seen)
        self.assertIn("hf:qwen/qwen3.8-27b", seen)


class RedditOrderTests(unittest.TestCase):
    def test_project_sub_is_fetched_first(self):
        calls = []

        def fake_fetch(url, _up):
            calls.append(url)
            raise OSError("synthetic")

        with patch.object(reddit, "fetch", side_effect=fake_fetch), \
             patch.object(reddit, "atomic_write_json"), \
             patch.object(reddit, "out_path", return_value="/tmp/x.json"), \
             patch.object(reddit.time, "sleep"):
            reddit.main()
        self.assertIn(f"/r/{reddit.PROJECT_SUB}/", calls[0])

    def test_429_waits_and_retries_once_then_succeeds(self):
        state = {"n": 0}
        sleeps = []

        def fake_fetch(url, _up):
            if f"/r/{reddit.PROJECT_SUB}/" in url:
                state["n"] += 1
                if state["n"] == 1:
                    raise urllib.error.HTTPError(url, 429, "Too Many Requests", {"Retry-After": "7"}, None)
                return '<feed xmlns="http://www.w3.org/2005/Atom"></feed>'
            raise OSError("synthetic")

        with patch.object(reddit, "fetch", side_effect=fake_fetch), \
             patch.object(reddit, "atomic_write_json"), \
             patch.object(reddit, "out_path", return_value="/tmp/x.json"), \
             patch.object(reddit.time, "sleep", side_effect=sleeps.append):
            rc = reddit.main()
        self.assertEqual(state["n"], 2)       # original + exactly one retry
        self.assertIn(7.0, sleeps)            # honored Retry-After
        self.assertEqual(rc, 0)               # one healthy feed is not a total outage

    def test_retry_after_is_capped(self):
        err = urllib.error.HTTPError("u", 429, "x", {"Retry-After": "3600"}, None)
        self.assertEqual(reddit._retry_after(err), reddit.RATE_LIMIT_WAIT_MAX)
        self.assertIsNone(reddit._retry_after(urllib.error.HTTPError("u", 500, "x", {}, None)))


if __name__ == "__main__":
    unittest.main()
