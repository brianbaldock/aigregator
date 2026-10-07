"""Synthetic Atom and loader coverage for Reddit project discovery."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "fetchers"))
sys.path.insert(0, str(REPO / "scripts"))
import reddit  # noqa: E402
from project_discovery import load_projects  # noqa: E402

NOW = datetime(2026, 10, 7, 3, tzinfo=timezone.utc)


def fixture_entry(title, published, updated, content):
    return f"""<entry>
<title>{title}</title><link href="https://www.reddit.com/r/BestGitHubRepos/comments/synthetic"/>
<published>{published}</published><updated>{updated}</updated>
<content type="html">{content}</content></entry>"""


def fixture_feed(*entries):
    return '<?xml version="1.0"?><feed xmlns="http://www.w3.org/2005/Atom">' + "".join(entries) + "</feed>"


class RedditProjectTests(unittest.TestCase):
    def setUp(self):
        self.original_now = reddit.NOW
        reddit.NOW = NOW

    def tearDown(self):
        reddit.NOW = self.original_now

    def test_parses_encoded_repo_links_and_preserves_exact_url(self):
        body = fixture_feed(fixture_entry(
            "Synthetic tool", "2026-10-07T02:00:00Z", "2026-10-07T02:30:00Z",
            '&lt;p&gt;Synthetic: &lt;a href="https://github.com/Example/Tool/?ref=reddit"&gt;repo&lt;/a&gt;&lt;/p&gt;'))
        items = reddit.parse_atom(body, reddit.PROJECT_SUB)
        self.assertEqual(items[0]["project_urls"], ["https://github.com/Example/Tool/?ref=reddit"])
        self.assertEqual(items[0]["published"], "2026-10-07T02:00:00+00:00")

    def test_rejects_non_root_github_and_non_github_links(self):
        content = "".join(
            f'&lt;a href="{url}"&gt;synthetic&lt;/a&gt;' for url in [
                "https://github.com/Example",
                "https://github.com/Example/Tool/issues/1",
                "https://github.com/topics/ai",
                "https://github.com.evil.test/Example/Tool",
                "https://github.com/user:secret@github.com/Example/Tool",
                "https://example.test/Example/Tool",
                "https://github.com/Example/%2e%2e/Tool",
            ])
        body = fixture_feed(fixture_entry(
            "Synthetic links", "2026-10-07T02:00:00Z", "2026-10-07T02:00:00Z", content))
        self.assertEqual(reddit.parse_atom(body, reddit.PROJECT_SUB)[0]["project_urls"], [])

    def test_uses_created_date_and_strictly_filters_project_dates(self):
        entries = [
            fixture_entry("created wins", "2026-10-07T01:00:00Z", "2026-09-01T00:00:00Z",
                          '&lt;a href="https://github.com/A/One"&gt;x&lt;/a&gt;'),
            fixture_entry("stale", "2026-10-05T01:00:00Z", "2026-10-07T02:00:00Z",
                          '&lt;a href="https://github.com/A/Two"&gt;x&lt;/a&gt;'),
            fixture_entry("future", "2026-10-08T01:00:00Z", "2026-10-07T02:00:00Z",
                          '&lt;a href="https://github.com/A/Three"&gt;x&lt;/a&gt;'),
            fixture_entry("missing", "", "2026-10-07T02:00:00Z",
                          '&lt;a href="https://github.com/A/Four"&gt;x&lt;/a&gt;'),
        ]
        items = reddit.parse_atom(fixture_feed(*entries), reddit.PROJECT_SUB)
        self.assertEqual([item["title"] for item in items], ["created wins"])

    def test_ordinary_subreddit_remains_updated_date_based(self):
        body = fixture_feed(fixture_entry(
            "Synthetic ordinary", "2026-09-01T00:00:00Z", "2026-10-07T02:00:00Z",
            "Synthetic ordinary post"))
        items = reddit.parse_atom(body, "LocalLLaMA")
        self.assertEqual(len(items), 1)
        self.assertNotIn("project_urls", items[0])

    def test_loader_emits_attributed_canonical_project_once(self):
        rows = reddit.parse_atom(fixture_feed(fixture_entry(
            "Synthetic AI project post", "2026-10-07T02:00:00Z", "2026-10-07T02:00:00Z",
            ('&lt;a href="https://github.com/Owner/Repo"&gt;one&lt;/a&gt; '
             '&lt;a href="https://github.com/owner/repo/"&gt;duplicate&lt;/a&gt;'))), reddit.PROJECT_SUB)
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "reddit_items.json").write_text(json.dumps(rows))
            projects = load_projects(directory, NOW)
        self.assertEqual(len(projects), 1)
        project = projects[0]
        self.assertEqual(project["url"], "https://github.com/Owner/Repo")
        self.assertEqual(project["title"], "Owner/Repo")
        self.assertEqual(project["source"], "GitHub:Owner/Repo")
        self.assertEqual(project["published_kind"], "discovery_post")
        self.assertEqual(project["discovery_source"], "r/BestGitHubRepos")
        self.assertTrue(project["requires_ai_review"])
        self.assertIn("Shared on r/BestGitHubRepos:", project["summary"])
        self.assertEqual(project["flags"], [])
        self.assertNotIn("cross_source", project["flags"])

    def test_loader_rejects_stale_future_missing_and_malformed_candidates(self):
        rows = [
            {"subreddit": reddit.PROJECT_SUB, "published": value, "project_urls": urls}
            for value, urls in [
                ("2026-10-05T00:00:00Z", ["https://github.com/A/Stale"]),
                ("2026-10-08T00:00:00Z", ["https://github.com/A/Future"]),
                ("", ["https://github.com/A/Missing"]),
                ("2026-10-07T02:00:00Z", ["https://github.com/A/Repo/issues/1"]),
            ]
        ]
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "reddit_items.json").write_text(json.dumps(rows))
            self.assertEqual(load_projects(directory, NOW), [])

    def test_total_feed_outage_writes_diagnostic_empty_and_fails(self):
        written = []
        with patch.object(reddit, "fetch", side_effect=OSError("synthetic outage")), \
             patch.object(reddit, "atomic_write_json", side_effect=lambda _path, data: written.append(data)), \
             patch.object(reddit, "out_path", return_value="/tmp/synthetic-reddit.json"), \
             patch.object(reddit.time, "sleep"):
            self.assertEqual(reddit.main(), 1)
        self.assertEqual(written, [[]])

    def test_healthy_empty_feeds_succeed(self):
        written = []
        with patch.object(reddit, "fetch", return_value=fixture_feed()), \
             patch.object(reddit, "atomic_write_json", side_effect=lambda _path, data: written.append(data)), \
             patch.object(reddit, "out_path", return_value="/tmp/synthetic-reddit.json"), \
             patch.object(reddit.time, "sleep"):
            self.assertEqual(reddit.main(), 0)
        self.assertEqual(written, [[]])


if __name__ == "__main__":
    unittest.main()
