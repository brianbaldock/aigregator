"""Final-artifact gate tests. All data here is synthetic, not scraped evidence."""
import importlib.util
from pathlib import Path
import sys
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / 'scripts'))
import test_digest_contract as fixture


class FinalArtifactTests(unittest.TestCase):
    def test_changed_dashboard_cannot_pass_final_gate(self):
        spec = importlib.util.find_spec('validate_digest')
        self.assertIsNotNone(spec, 'the final artifact gate must exist')
        from validate_digest import validate_artifact
        items = [fixture.news_item()]
        cur = fixture.curation_for(items)
        result, clean = fixture.RendererContractTests().render(items, cur)
        self.assertEqual(result.returncode, 0, result.stderr)
        ok = validate_artifact(items, cur, [], clean, '2026-10-06')
        self.assertEqual(ok['errors'], [], ok)
        self.assertEqual(ok['counts']['candidates'], 1)
        corrupt = clean.replace('1 stories', '99 stories')
        self.assertNotEqual(clean, corrupt, 'sabotage must land')
        broken = validate_artifact(items, cur, [], corrupt, '2026-10-06')
        self.assertTrue(broken['errors'])
        self.assertTrue(any('dashboard' in err.lower() for err in broken['errors']))
    def test_each_artifact_mutation_fails_after_a_passing_control(self):
        from validate_digest import validate_artifact
        items = [fixture.news_item()]
        cur = fixture.curation_for(items)
        market = dict(question='Will model X ship by December 31, 2026?', yes_pct=0.5,
                      change_24h_pp=0, volume_usd=0, url='https://polymarket.com/event/model-x')
        result, clean = fixture.RendererContractTests().render(items, cur, [market])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(validate_artifact(items, cur, [market], clean, '2026-10-06')['errors'])
        row = next(line for line in clean.splitlines() if line.startswith('- 6 '))
        market_row = next(line for line in clean.splitlines() if line.startswith('- **') and '[Polymarket]' in line)
        mutations = {
            'uncurated market annotation': clean.replace(market_row, market_row + ' This outcome is guaranteed.'),
            'top mention count': clean.replace('(none) ×0', '(none) ×99'),
            'theme count': clean.replace('models×1', 'models×99'),
            'summary drift': clean.replace('The lab published model weights.', 'The lab acquired Mars.'),
            'extra uncurated paragraph': clean.replace(row, row + '\nUncurated extra assertion.'),
            'section count': clean.replace('_1 item ·', '_99 items ·'),
            'citation': clean.replace('publisher1.test/2026/', 'different.test/2026/'),
            'score': clean.replace('- 6 ', '- 99 '),
            'edition': clean.replace('# 2026-10-06', '# 2026-10-05'),
            'missing row': clean.replace(row, ''),
            'duplicate row': clean.replace(row, row + '\n' + row),
            'sentiment': clean.replace('+0.0 sentiment', '+9.0 sentiment'),
            'missing section': clean.replace('## 🔬 Research', '## Wrong heading'),
            'market count': clean.replace('_1 markets', '_99 markets'),
            'market probability': clean.replace('0.5% Yes', 'None% Yes'),
            'expired question': clean.replace('December 31, 2026?', 'September 30, 2026?'),
            'TLDR': clean.replace('1. 6 🟡', '9. 6 🟡'),
        }
        for name, corrupt in mutations.items():
            with self.subTest(mutation=name):
                self.assertNotEqual(corrupt, clean, 'sabotage did not land')
                report = validate_artifact(items, cur, [market], corrupt, '2026-10-06')
                self.assertTrue(report['errors'], report)
    def test_report_preserves_whole_limitations(self):
        from validate_digest import _merge_reports
        report = _merge_reports({'limitations': 'Not a fact check.'}, {'limitations': ['Identity only.']})
        self.assertEqual(report['limitations'], ['Not a fact check.', 'Identity only.'])

    def test_renderer_itself_refuses_a_corrupted_dashboard(self):
        import contextlib
        import io
        import json
        import tempfile
        from unittest.mock import patch
        import write_digest
        items = [fixture.news_item()]
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / 'digest_items.json').write_text(json.dumps(items))
            (root / 'curation.json').write_text(json.dumps(fixture.curation_for(items)))
            (root / 'polymarket.json').write_text('[]')
            output = root / '2026-10-06.md'
            argv = ['write_digest', '--items', str(root / 'digest_items.json'), '--curation', str(root / 'curation.json'),
                    '--date', '2026-10-06', '--out', str(output), '--digests-dir', td]
            with patch.object(sys, 'argv', argv), patch.object(write_digest, 'dashboard_line', return_value=['> **📊 TODAY:** 99 stories']), \
                 contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):
                    write_digest.main()
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
