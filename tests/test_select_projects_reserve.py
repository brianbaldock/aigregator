"""Regression tests: the projects section reserves slots for repository discoveries.

r/BestGitHubRepos discoveries score 4 (single Reddit discovery source) and lose
every slot of the projects section to multi-source news at 10-11, so the GitHub
discovery stream could never render on a normal news day (2026-11-11: 25
discovered, 3 passed the curation AI-relevance review, 0 rendered). select_items
must reserve up to PROJECT_GITHUB_RESERVE projects slots for GitHub-sourced
items that survived curation. Fixtures are synthetic.
"""
import sys
import unittest
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))

from write_digest import PROJECT_GITHUB_RESERVE, select_items


def pool(*, news_scores: list[int], github_scores: list[int]) -> list[dict[str, Any]]:
    """digest_items-style records, every url mapped to section 'projects'."""
    items: list[dict[str, Any]] = []
    n = 0
    for score in news_scores:
        n += 1
        items.append({"url": f"https://outlet{n}.test/story-{n}", "score": score,
                      "source": f"Outlet {n}", "tier": "news"})
    for score in github_scores:
        n += 1
        items.append({"url": f"https://github.com/owner/repo{n}", "score": score,
                      "source": f"GitHub:owner/repo{n}", "tier": "projects"})
    return items


def curation_for(items: list[dict[str, Any]], tldr: tuple[str, ...] = ()) -> dict[str, Any]:
    return {
        "exclusions": {},
        "tldr_order": list(tldr),
        "items": {it["url"]: {"section": "projects"} for it in items},
    }


def projects_urls(items: list[dict[str, Any]], curation: dict[str, Any]) -> list[str]:
    sections = select_items(items, curation)
    return [it["url"] for it in sections["projects"]]


class ProjectsReserveTests(unittest.TestCase):
    def test_repos_survive_heavy_news_day(self):
        """The 2026-11-11 shape: five news at 10-11 outrank every repo at 4."""
        items = pool(news_scores=[11, 10, 10, 10, 10], github_scores=[4, 4, 4])
        picked = projects_urls(items, curation_for(items))
        gh = [u for u in picked if u.startswith("https://github.com/")]
        news = [u for u in picked if u not in gh]
        self.assertEqual(len(picked), 5)
        self.assertEqual(len(gh), PROJECT_GITHUB_RESERVE)
        # The two lowest-ranked news items give way, the top three stay.
        self.assertEqual(len(news), 3)
        self.assertEqual(sorted(news), [
            "https://outlet1.test/story-1", "https://outlet2.test/story-2",
            "https://outlet3.test/story-3"])

    def test_single_repo_no_filler(self):
        """One surviving repo reserves one slot, not two."""
        items = pool(news_scores=[11, 10, 10, 10, 10], github_scores=[4])
        picked = projects_urls(items, curation_for(items))
        self.assertEqual(len(picked), 5)
        self.assertEqual(sum(u.startswith("https://github.com/") for u in picked), 1)

    def test_no_repos_unchanged(self):
        """No GitHub survivors: selection is exactly the pre-reserve behavior."""
        items = pool(news_scores=[11, 10, 10, 10, 10], github_scores=[])
        picked = projects_urls(items, curation_for(items))
        self.assertEqual(picked, [it["url"] for it in sorted(
            items, key=lambda it: -it["score"])])

    def test_reserve_is_a_floor_extra_repos_fill_leftover_slots(self):
        """The reserve is a minimum, not a cap: on a light news day leftover
        repos still fill the section exactly as before the reserve existed."""
        items = pool(news_scores=[10], github_scores=[4, 4, 4, 4])
        picked = projects_urls(items, curation_for(items))
        gh = [u for u in picked if u.startswith("https://github.com/")]
        self.assertEqual(len(picked), 5)
        self.assertGreaterEqual(len(gh), PROJECT_GITHUB_RESERVE)

    def test_excess_repos_do_not_evict_the_top_news(self):
        """More surviving repos than the reserve: news still gets its slots."""
        items = pool(news_scores=[11, 10, 10, 10, 10], github_scores=[4, 4, 4, 4])
        picked = projects_urls(items, curation_for(items))
        gh = [u for u in picked if u.startswith("https://github.com/")]
        news = [u for u in picked if not u.startswith("https://github.com/")]
        self.assertEqual(len(gh), PROJECT_GITHUB_RESERVE)
        self.assertEqual(len(news), 3)
        self.assertEqual(news[0], "https://outlet1.test/story-1")

    def test_tldr_github_pick_counts_toward_reserve(self):
        """A TLDR pick that is itself a GitHub project consumes one reserve slot."""
        items = pool(news_scores=[11, 10, 10, 10, 10], github_scores=[4, 4])
        gh_tldr = "https://github.com/owner/repo6"  # last appended github url
        picked = projects_urls(items, curation_for(items, tldr=(gh_tldr,)))
        gh = [u for u in picked if u.startswith("https://github.com/")]
        self.assertEqual(len(gh), PROJECT_GITHUB_RESERVE)
        self.assertEqual(gh.count(gh_tldr), 1)

    def test_tldr_filled_section_stays_within_limit(self):
        """Belt and braces: a TLDR reserve that fills the section admits no more."""
        items = pool(news_scores=[11, 10, 10, 10, 10], github_scores=[4, 4, 4])
        tldr = tuple(it["url"] for it in items if it["tier"] == "news")
        picked = projects_urls(items, curation_for(items, tldr=tldr))
        self.assertEqual(len(picked), 5)
        self.assertFalse(any(u.startswith("https://github.com/") for u in picked))

    def test_other_sections_keep_pure_score_order(self):
        """The reserve is projects-only; other sections still rank by score alone."""
        items = pool(news_scores=[11, 10], github_scores=[4])
        curation = curation_for(items)
        for it in items:
            curation["items"][it["url"]]["section"] = "tools"
        picked = [it["url"] for it in select_items(items, curation)["tools"]]
        self.assertEqual(picked, [
            "https://outlet1.test/story-1", "https://outlet2.test/story-2",
            "https://github.com/owner/repo3"])


if __name__ == "__main__":
    unittest.main()