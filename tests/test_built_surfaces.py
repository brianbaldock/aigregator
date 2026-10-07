"""Use the actual HTML/feed builders, with network checks isolated at the edge."""
from contextlib import ExitStack, redirect_stdout
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build
import publication_checks as checks
import test_digest_contract as fixture


class BuiltSurfaceTests(unittest.TestCase):
    def build_fixture(self, root):
        root = Path(root)
        docs, digests = root / 'docs', root / 'digests'
        docs.mkdir()
        digests.mkdir()
        result, markdown = fixture.RendererContractTests().render()
        self.assertEqual(result.returncode, 0, result.stderr)
        digest = digests / '2026-10-06.md'
        digest.write_text(markdown)
        with ExitStack() as stack, redirect_stdout(io.StringIO()):
            for name, value in [('DOCS_DIR', docs), ('DOCS_DIGESTS', docs / 'digests'), ('DIGESTS_DIR', digests)]:
                stack.enter_context(patch.object(build, name, value))
            stack.enter_context(patch.object(build, 'validate_links_live', return_value=[]))
            stack.enter_context(patch.object(build, 'validate_bluesky_urls', return_value=[]))
            entries = build.build_digest_pages()
            build.build_index(entries)
            build.build_feeds(entries)
            build.build_archive(entries)
        return docs, digest

    def test_feed_payload_drift_fails_even_if_date_is_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            docs, digest = self.build_fixture(td)
            clean = checks.check_docs(docs, digest, '2026-10-06')
            self.assertFalse(clean['errors'], clean)
            for name in ('feed.xml', 'atom.xml'):
                with self.subTest(surface=name):
                    path = docs / name
                    original = path.read_text()
                    changed = original.replace('The lab published model weights.', 'Unrelated stale story.')
                    self.assertNotEqual(changed, original)
                    path.write_text(changed)
                    self.assertIn('2026-10-06', changed)
                    report = checks.check_docs(docs, digest, '2026-10-06')
                    self.assertTrue(report['errors'], report)
                    path.write_text(original)

    def test_wrong_latest_archive_is_not_a_valid_current_publication(self):
        with tempfile.TemporaryDirectory() as td:
            docs, digest = self.build_fixture(td)
            path = docs / 'archive.json'
            entries = json.loads(path.read_text())
            entries.insert(0, {**entries[0], 'slug': '2026-10-07'})
            path.write_text(json.dumps(entries))
            report = checks.check_docs(docs, digest, '2026-10-06')
            self.assertTrue(report['errors'], report)


if __name__ == '__main__':
    unittest.main()
