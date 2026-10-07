"""Check the public method text against live ranking policy, not prose literals."""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build
import scoring_policy
import merge_score


import json
from datetime import datetime, timezone
import project_discovery


class ScoringMethodTests(unittest.TestCase):
    def test_project_score_uses_shared_policy(self):
        with tempfile.TemporaryDirectory() as td:
            row = dict(subreddit='BestGitHubRepos', published='2026-10-06T12:00:00+00:00',
                       url='https://www.reddit.com/r/BestGitHubRepos/comments/example/post/',
                       project_urls=['https://github.com/example/ai-notes'])
            (Path(td) / 'reddit_items.json').write_text(json.dumps([row]))
            with patch.object(scoring_policy, 'BASE_WEIGHT', 7):
                projects = project_discovery.load_projects(td, now=datetime(2026, 10, 6, 12, tzinfo=timezone.utc))
                self.assertEqual(len(projects), 1)
                self.assertEqual(projects[0]['score'], scoring_policy.score_item(projects[0]))

    def test_about_uses_shared_policy_instead_of_stale_eight_point_scale(self):
        with tempfile.TemporaryDirectory() as td:
            with patch.object(build, 'DOCS_DIR', Path(td)), patch.object(build, 'html_shell', side_effect=lambda **kw: kw['body']):
                build.build_about([])
            html = (Path(td) / 'about.html').read_text()
        self.assertNotIn('1 through 8', html)
        self.assertIn('ranking heuristic', html)
        self.assertIn(f'{scoring_policy.BASE_WEIGHT} × credibility', html)
        self.assertIn(f'{scoring_policy.CORROBORATION_BONUS} per additional', html)
        self.assertIn('not a probability', html)

    def test_cluster_score_and_public_policy_use_the_same_arithmetic(self):
        items = [merge_score._item('Reuters', 5, 'Novel model release',
            'https://www.reuters.com/technology/novel-model-release', 'Weights released.',
            '2026-10-06T00:00:00+00:00', via_kagi=True)]
        with patch.object(scoring_policy, 'BASE_WEIGHT', 7):
            result = merge_score.cluster_and_score(items)[0]
            self.assertEqual(result['score'], scoring_policy.score_item(result))


if __name__ == '__main__':
    unittest.main()
