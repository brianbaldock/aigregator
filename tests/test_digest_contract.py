"""Offline renderer and publication-contract regressions; fixtures are synthetic."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))


def news_item(index=1, **updates) -> dict[str, Any]:
    url = f'https://publisher{index}.test/2026/10/06/story'
    host = f'publisher{index}.test'
    item = dict(url=url, title=f'Lab {index} releases a model', summary='The lab published model weights.',
                source=host, domain=host, tier='news', credibility=3, score=6,
                source_count=1, source_domains=[host], sources=[host],
                source_urls=[dict(url=url, domain=host, source=host)], flags=[],
                sentiment=0, via_kagi=False, dated=True, published='2026-10-06T01:00:00+00:00')
    item.update(updates)
    return item


def curation_for(items) -> dict[str, Any]:
    return dict(subtitle='Labs published model weights today.',
                tldr_order=[i['url'] for i in items if i['tier'] == 'news'][:6],
                tldr_blurbs={i['url']: i['summary'] for i in items if i['tier'] == 'news'},
                items={i['url']: dict(title=i['title'], summary=i['summary'], themes=['models'],
                                     section='models') for i in items})


class RendererContractTests(unittest.TestCase):
    def render(self, items=None, curation=None, markets=None, manifest=None):
        items = items if items is not None else [news_item()]
        curation = curation if curation is not None else curation_for(items)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'digest_items.json').write_text(json.dumps(items))
            (root / 'curation.json').write_text(json.dumps(curation))
            (root / 'polymarket.json').write_text(json.dumps(markets or []))
            if manifest is not None:
                (root / 'gather_manifest.json').write_text(json.dumps(manifest))
            result = subprocess.run([sys.executable, str(REPO / 'scripts/write_digest.py'),
                '--items', str(root / 'digest_items.json'), '--curation', str(root / 'curation.json'),
                '--date', '2026-10-06', '--digests-dir', td, '--out', str(root / '2026-10-06.md')],
                text=True, capture_output=True)
            path = root / '2026-10-06.md'
            return result, path.read_text() if path.exists() else ''

    def test_optional_source_outage_is_reader_visible(self):
        healthy, clean = self.render(manifest={'reddit': {'status': 'OK'}})
        self.assertEqual(healthy.returncode, 0, healthy.stderr)
        self.assertNotIn('Collection gaps:', clean)
        failed, text = self.render(manifest={'reddit': {'status': 'FAIL'}, 'polymarket': {'status': 'TIMEOUT'}})
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertIn('Collection gaps:', text)
        self.assertIn('Reddit', text)
        self.assertIn('Polymarket', text)

    def test_missing_news_overlays_cannot_render(self):
        items = [news_item(i) for i in range(1, 7)]
        curation = curation_for(items)
        curation['items'] = {}
        result, text = self.render(items, curation)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(text, '')
        self.assertIn('unaccounted', result.stderr.lower())

    def test_tldr_pick_survives_section_limit(self):
        items = [news_item(i) for i in range(1, 10)]
        cur = curation_for(items)
        cur['tldr_order'] = [items[-1]['url']]
        result, text = self.render(items, cur)
        self.assertEqual(result.returncode, 0, result.stderr)
        body = text.split('## 🧠 Models & Releases', 1)[1]
        self.assertIn(items[-1]['url'], body)
        self.assertIn('_5 items', body)

    def test_inconsistent_source_counts_and_numbers_cannot_render(self):
        for changes in ({'source_count': 99}, {'score': 99}, {'flags': ['cross_source']},
                        {'sentiment': float('nan')}, {'credibility': True}):
            with self.subTest(changes=changes):
                item = news_item(**changes)
                result, text = self.render([item])
                self.assertNotEqual(result.returncode, 0, result.stderr)
                self.assertEqual(text, '')

    def test_prior_sentiments_exclude_future_and_outside_calendar_window(self):
        from write_digest import read_prior_sentiments
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for day in ('2026-09-01', '2026-10-01', '2026-10-05', '2026-10-06', '2026-10-07'):
                (root / f'{day}.md').write_text('> +0.2 sentiment')
            self.assertEqual(read_prior_sentiments(root, '2026-10-06'), [0.2, 0.2])

    def test_research_keeps_all_retained_citations(self):
        item = news_item(tier='research', source_count=2, score=9, flags=['cross_source'])
        extra = dict(url='https://second.test/2026/10/06/research', domain='second.test', source='Second')
        item['source_urls'].append(extra)
        item['source_domains'].append(extra['domain'])
        result, text = self.render([item])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(extra['url'], text)

    def test_discourse_cap_is_part_of_final_selection(self):
        items = [news_item()]
        for index in range(10, 16):
            item = news_item(index, tier='social', source='HN', domain='news.ycombinator.com',
                url=f'https://news.ycombinator.com/item?id={index}', source_domains=['news.ycombinator.com'])
            item['source_urls'] = [dict(url=item['url'], source='HN', domain=item['domain'])]
            items.append(item)
        result, text = self.render(items)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(items[1]['url'], text)
        self.assertNotIn(items[-1]['url'], text)

    def test_zero_percent_is_not_missing_data(self):
        for zero in (0, 0.0):
            with self.subTest(zero_type=type(zero).__name__):
                result, text = self.render(markets=[dict(question='Will AI model X ship by December 31, 2026?',
                    yes_pct=zero, change_24h_pp=zero, volume_usd=zero,
                    url='https://polymarket.com/event/model-x')])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('0% Yes', text)
                self.assertNotIn('None%', text)

    def test_invalid_optional_markets_are_omitted_before_dashboard(self):
        good = dict(question='Will AI model X ship by December 31, 2026?', yes_pct=0.5,
                    change_24h_pp=0, volume_usd=20, market_id='good', url='https://polymarket.com/event/model-x')
        for change in ({'yes_pct': 101}, {'yes_pct': float('nan')}, {'yes_pct': True},
                       {'yes_pct': '12'}, {'volume_usd': -1}, {'change_24h_pp': float('inf')},
                       {'question': 'Gemini 4.0 released by September 30, 2026?'},
                       {'closed': True}, {'acceptingOrders': False}, {'event': None},
                       {'market_id': ['bad']}, {'endDate': '2026-99-99'},
                       {'event': {'closed': 'false'}}, {'volume_usd': 10 ** 1000},
                       {'question': '<img src=x onerror=alert(1)>'}):
            with self.subTest(change=change):
                bad = {**good, 'question': 'Will an invalid record ship by December 31, 2026?', 'market_id': 'bad', **change}
                result, text = self.render(markets=[bad, good])
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('_1 markets', text)
                self.assertIn('1 AI markets tracked', text)
                self.assertIn('0.5% Yes', text)
                self.assertIn('omitted', text.lower())
                self.assertIn('market', result.stderr.lower())


if __name__ == '__main__':
    unittest.main()
