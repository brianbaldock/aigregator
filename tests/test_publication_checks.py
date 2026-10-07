"""Offline fixtures for publication provenance enforcement."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import sys
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import publication_checks as checks


class PublicationChecksTests(unittest.TestCase):
    def fixture(self, root, *, mutate=None):
        root = Path(root)
        now = datetime(2026, 10, 6, 12, tzinfo=timezone.utc)
        manifest = {}
        for name in checks.EXPECTED_SOURCES:
            filename = checks.gather.OUTPUT_FILE.get(name)
            if name == "kagi":
                path = root / "kagi" / "q.json"
                path.parent.mkdir()
                payload = {"data": {"search": [{"url": "https://example.test/kagi"}]}}
            elif name == "opensource":
                path = root / filename
                payload = {bucket: [] for bucket in checks.gather.OPENSOURCE_BUCKETS}
            else:
                path = root / filename
                payload = [{"url": f"https://example.test/{name}"}] if name == "rss" else []
            path.write_text(json.dumps(payload))
            count = 1 if name in {"rss", "kagi"} else 0
            output = [{"path": str(path.relative_to(root)),
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}]
            manifest[name] = {"status": "OK" if count else "EMPTY", "rc": 0, "count": count,
                              "generation_id": "same-generation", "collected_at": now.isoformat(),
                              "outputs": output}
        if mutate:
            mutate(root, manifest)
        (root / "gather_manifest.json").write_text(json.dumps(manifest))
        return now

    def test_valid_manifest_and_hash_mutation(self):
        with tempfile.TemporaryDirectory() as td:
            now = self.fixture(td)
            report, consumed = checks.check_provenance(td, "2026-10-06", now=now)
            self.assertFalse(report["errors"], report)
            self.assertTrue(consumed)
            (Path(td) / "rss_items.json").write_text("[]")
            report, _ = checks.check_provenance(td, "2026-10-06", now=now)
            self.assertTrue(any("hash mismatch" in x for x in report["errors"]), report)

    def test_rejects_in_progress_traversal_and_false_ok(self):
        cases = {
            "in progress": lambda root, m: m["rss"].update(status="IN_PROGRESS"),
            "traversal": lambda root, m: m["rss"]["outputs"][0].update(path="../outside.json"),
            "false ok": lambda root, m: m["rss"].update(count=0),
        }
        for label, mutate in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as td:
                now = self.fixture(td, mutate=mutate)
                report, _ = checks.check_provenance(td, "2026-10-06", now=now)
                self.assertTrue(report["errors"], report)

    def test_failed_source_cannot_leave_consumable_raw_data(self):
        with tempfile.TemporaryDirectory() as td:
            now = self.fixture(td)
            clean, _ = checks.check_provenance(td, '2026-10-06', now=now)
            self.assertFalse(clean['errors'], clean)
            path = Path(td) / 'gather_manifest.json'
            manifest = json.loads(path.read_text())
            manifest['rss'].update(status='FAIL', rc=1, count=None, outputs=[])
            path.write_text(json.dumps(manifest))
            self.assertTrue((Path(td) / 'rss_items.json').is_file())
            report, _ = checks.check_provenance(td, '2026-10-06', now=now)
            self.assertTrue(report['errors'], report)

    def test_boolean_manifest_numbers_are_not_integer_success(self):
        with tempfile.TemporaryDirectory() as td:
            now = self.fixture(td)
            path = Path(td) / 'gather_manifest.json'
            before = path.read_text()
            manifest = json.loads(before)
            manifest['rss'].update(rc=False, count=True)
            path.write_text(json.dumps(manifest))
            self.assertNotEqual(path.read_text(), before)
            report, _ = checks.check_provenance(td, '2026-10-06', now=now)
            self.assertTrue(report['errors'], report)

    def test_symlinked_kagi_directory_is_not_provenance(self):
        with tempfile.TemporaryDirectory() as td:
            now = self.fixture(td)
            root = Path(td)
            (root / 'kagi').rename(root / 'elsewhere')
            (root / 'kagi').symlink_to(root / 'elsewhere', target_is_directory=True)
            self.assertTrue((root / 'kagi').is_symlink())
            report, _ = checks.check_provenance(td, '2026-10-06', now=now)
            self.assertTrue(report['errors'], report)

    def test_busy_lock_is_refused_without_leaking_descriptors(self):
        import os
        import fcntl
        with tempfile.TemporaryDirectory() as td:
            now = self.fixture(td)
            with (Path(td) / '.gather.lock').open('w') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                before = len(os.listdir('/proc/self/fd'))
                report, _ = checks.check_provenance(td, '2026-10-06', now=now)
                self.assertTrue(report['errors'], report)
                self.assertEqual(len(os.listdir('/proc/self/fd')), before)

    def test_legacy_replay_is_explicitly_unverified_not_retrofitted(self):
        with tempfile.TemporaryDirectory() as td:
            now = self.fixture(td)
            path = Path(td) / 'gather_manifest.json'
            manifest = json.loads(path.read_text())
            for entry in manifest.values():
                for key in ('generation_id', 'collected_at', 'outputs', 'rc'):
                    entry.pop(key)
            path.write_text(json.dumps(manifest))
            before = path.read_bytes()
            strict, _ = checks.check_provenance(td, '2026-10-06', now=now)
            self.assertTrue(strict['errors'])
            replay, consumed = checks.check_provenance(td, '2026-10-06', now=now, historical_replay=True)
            self.assertFalse(replay['errors'], replay)
            self.assertTrue(consumed)
            self.assertIs(replay['provenance_verified'], False)
            self.assertTrue(any('unverified' in warning for warning in replay['warnings']))
            self.assertEqual(path.read_bytes(), before)

    def test_replay_does_not_excuse_a_broken_modern_hash(self):
        with tempfile.TemporaryDirectory() as td:
            now = self.fixture(td)
            path = Path(td) / 'gather_manifest.json'
            manifest = json.loads(path.read_text())
            manifest['rss']['outputs'][0]['sha256'] = ''
            path.write_text(json.dumps(manifest))
            report, _ = checks.check_provenance(td, '2026-10-06', now=now, historical_replay=True)
            self.assertTrue(report['errors'], report)

    def test_project_lineage_uses_exact_post_pair_without_midnight_age_filter(self):
        with tempfile.TemporaryDirectory() as td:
            self.fixture(td)
            repo = 'https://github.com/example/local-notes'
            discussion = 'https://www.reddit.com/r/BestGitHubRepos/comments/example/post/'
            row = dict(subreddit='BestGitHubRepos', published='2026-10-06T10:00:00+00:00',
                       url=discussion, project_urls=[repo])
            (Path(td) / 'reddit_items.json').write_text(json.dumps([row]))
            item = dict(url=repo, tier='projects', discovery_url=discussion, source_urls=[dict(url=repo)])
            report = checks.check_lineage(td, [item], '2026-10-06')
            self.assertFalse(report['errors'], report)
            item['discovery_url'] = 'https://www.reddit.com/r/BestGitHubRepos/comments/different/post/'
            report = checks.check_lineage(td, [item], '2026-10-06')
            self.assertTrue(report['errors'], report)

    def test_lineage_rejects_fabricated_consistent_citation(self):
        with tempfile.TemporaryDirectory() as td:
            self.fixture(td)
            report = checks.check_lineage(td, [{"source_urls": [{"url": "https://forged.test/a"}]}], "2026-10-06")
            self.assertTrue(report["errors"], report)


if __name__ == "__main__":
    unittest.main()
