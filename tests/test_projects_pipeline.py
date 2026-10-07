"""Synthetic integration tests for the Reddit discovery-to-digest path."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import test_digest_contract as fixture
REPO = Path(__file__).resolve().parents[1]


class ProjectPipelineTests(unittest.TestCase):
    def project(self):
        item = fixture.news_item(tier='projects', title='example/local-notes', source='GitHub:example/local-notes',
            credibility=2, score=4, url='https://github.com/example/local-notes', domain='github.com',
            source_domains=['github.com'], requires_ai_review=True, discovery_source='r/BestGitHubRepos',
            discovery_url='https://www.reddit.com/r/BestGitHubRepos/comments/example/post/')
        item['source_urls'] = [dict(url=item['url'], source=item['source'], domain=item['domain'])]
        return item

    def test_explicit_ai_fit_review_then_projects_not_news(self):
        project = self.project()
        items = [fixture.news_item(), project]
        cur = fixture.curation_for(items)
        result, _ = fixture.RendererContractTests().render(items, cur)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('AI-fit', result.stderr)
        cur['items'][project['url']]['ai_relevance'] = 'The repository describes a local LLM note-taking application.'
        result, text = fixture.RendererContractTests().render(items, cur)
        self.assertEqual(result.returncode, 0, result.stderr)
        projects = text.split('## 🎨 Cool Projects & Novel Applications', 1)[1].split('## 💰', 1)[0]
        self.assertIn(project['url'], projects)
        self.assertIn(project['discovery_url'], projects)
        self.assertIn('1 stories', text)
        self.assertNotIn('▤×2', projects)

    def test_real_merge_loads_project_feed_without_social_duplication(self):
        now = datetime.now(timezone.utc).isoformat()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            wire = dict(source='Reuters', credibility=5, title='Chip maker announces unusual semiconductor factory',
                url='https://www.reuters.com/technology/synthetic-test-story', summary='A new factory was announced.', published=now)
            (root / 'rss_items.json').write_text(json.dumps([wire]))
            row = dict(subreddit='BestGitHubRepos', title='A local LLM notes application',
                summary='A project shared by its author.', published=now,
                url='https://www.reddit.com/r/BestGitHubRepos/comments/example/post/',
                project_urls=['https://github.com/example/local-notes'])
            (root / 'reddit_items.json').write_text(json.dumps([row]))
            output = root / 'digest_items.json'
            result = subprocess.run([sys.executable, str(REPO / 'scripts/merge_score.py'),
                '--in', td, '--out', str(output)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            items = json.loads(output.read_text())
            projects = [item for item in items if item['tier'] == 'projects']
            self.assertEqual(len(projects), 1, items)
            self.assertEqual(projects[0]['source_count'], 1)
            self.assertNotIn(row['url'], [item['url'] for item in items])


if __name__ == '__main__':
    unittest.main()
