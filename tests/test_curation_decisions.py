"""Curation omissions must be explicit and survive the batched assembly path."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import assemble_curation
import curate
import test_digest_contract as fixture


class CurationDecisionTests(unittest.TestCase):
    def test_assembly_preserves_explicit_exclusions(self):
        item = fixture.news_item()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            head = dict(subtitle='A quiet day.', tldr_order=[], tldr_blurbs={},
                        exclusions={item['url']: 'This is an undated hub, not a news story.'})
            (root / 'curation_head.json').write_text(json.dumps(head))
            (root / 'curation_items_01.json').write_text('{}')
            result, warnings = assemble_curation.assemble(td)
            self.assertEqual(result.get('exclusions'), head['exclusions'])
            _, _, errors = curate.validate(result, [item])
            self.assertFalse(errors, errors)

    def test_active_markup_cannot_become_public_digest_content(self):
        items = [fixture.news_item()]
        for text in ('<script>alert(1)</script>', '<img src=x onerror=alert(1)>', '[click](javascript:alert(1))'):
            for field in ('summary', 'title', 'subtitle', 'tldr_blurb', 'fallback_tldr'):
                with self.subTest(markup=text, field=field):
                    items = [fixture.news_item()]
                    cur = fixture.curation_for(items)
                    if field in ('summary', 'title'):
                        cur['items'][items[0]['url']][field] = text
                    elif field == 'subtitle':
                        cur[field] = text
                    elif field == 'tldr_blurb':
                        cur['tldr_blurbs'][items[0]['url']] = text
                    else:
                        cur['tldr_blurbs'] = {}
                        items[0]['summary'] = text
                    result, markdown = fixture.RendererContractTests().render(items, cur)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn('embedded HTML or links', result.stderr)
                    self.assertFalse(markdown)

    def test_unknown_overlay_url_is_not_silently_dropped(self):
        items = [fixture.news_item()]
        cur = fixture.curation_for(items)
        cur['items']['https://invented.test/fake'] = dict(title='Unknown', summary='Unknown.', themes=[], section='models')
        _, _, errors = curate.validate(cur, items)
        self.assertTrue(errors)


if __name__ == '__main__':
    unittest.main()
