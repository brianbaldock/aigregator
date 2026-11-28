"""Prove the weekly vault gate fails on every way the social worker can stop short.

These tests use real Git repositories (a bare remote plus clones), not mocks, because
the failure they guard is a Git-state failure: the W48 worker staged the edition bundle,
tripped on a false "trailing whitespace" report for the PDF, and stopped. The wrapper
still reported success because it only read the review database.
"""
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock


REPO = Path(__file__).resolve().parents[1]
# AIG_HANDOFF_UNDER_TEST lets a mutated copy of the handoff be run against these tests.
HELPER = Path(os.environ.get("AIG_HANDOFF_UNDER_TEST", str(REPO / "scripts" / "simplepost_weekly_handoff.py")))
spec = importlib.util.spec_from_file_location("weekly_handoff_vault_gate", HELPER)
assert spec is not None and spec.loader is not None
handoff = importlib.util.module_from_spec(spec)
spec.loader.exec_module(handoff)

SLUG = "2026-W48"
URL = "https://aigregator.news/weekly/2026-W48.html"
REL = "Projects/LinkedIn Posts/AIgregator Weekly"
# The renderer ASCII-encodes its streams, so the real PDF has no NUL bytes: Git treats it as
# text and `git diff --check` reports "trailing whitespace" on its xref table. Keep that shape.
PDF = b"%PDF-1.4\n0000000061 00000 n \n%%EOF\n"
LINKEDIN = ("Latest AI Weekly Roundup just dropped \u2192 %s\n" % URL).encode("utf-8")
EDITION = (
    "---\ntype: publication-edition\nedition: %s\n---\n\n# %s\n\n- Source: [Roundup](%s)\n" % (SLUG, SLUG, URL)
).encode("utf-8")
INDEX_HEAD = b"# AIgregator Weekly\n\n## Editions\n\n"
ENTRY = ("- [[%s/%s|%s]]\n" % (REL, SLUG, SLUG)).encode("utf-8")
GIT_ENV = dict(
    os.environ,
    GIT_AUTHOR_NAME="test", GIT_AUTHOR_EMAIL="test@example.invalid",
    GIT_COMMITTER_NAME="test", GIT_COMMITTER_EMAIL="test@example.invalid",
    GIT_TERMINAL_PROMPT="0",
)


def git(cwd, *args):
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True, env=GIT_ENV
    ).stdout.strip()


class VaultFixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.remote = self.base / "remote.git"
        self.vault = self.base / "vault"
        self.work = self.base / "work"
        self.work.mkdir()
        subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(self.remote)], check=True, env=GIT_ENV)
        subprocess.run(["git", "clone", "-q", str(self.remote), str(self.vault)], check=True, env=GIT_ENV,
                       capture_output=True)
        git(self.vault, "symbolic-ref", "HEAD", "refs/heads/main")
        (self.vault / REL).mkdir(parents=True)
        (self.vault / REL / "AIGregator Weekly.md").write_bytes(INDEX_HEAD)
        git(self.vault, "add", "-A")
        git(self.vault, "commit", "-q", "-m", "seed")
        git(self.vault, "push", "-q", "origin", "main")
        (self.work / ("%s-carousel.pdf" % SLUG)).write_bytes(PDF)
        (self.work / ("%s-linkedin.txt" % SLUG)).write_bytes(LINKEDIN)
        self.paths = handoff.artifact_paths(self.work, SLUG)

    def tearDown(self):
        self.temp.cleanup()

    def write_bundle(self, root=None, pdf=PDF, copy=LINKEDIN, edition=EDITION, entry=ENTRY):
        root = root or self.vault
        (root / REL / ("%s-carousel.pdf" % SLUG)).write_bytes(pdf)
        (root / REL / ("%s-linkedin.md" % SLUG)).write_bytes(copy)
        (root / REL / ("%s.md" % SLUG)).write_bytes(edition)
        (root / REL / "AIGregator Weekly.md").write_bytes(INDEX_HEAD + entry)

    def stage(self, root=None):
        git(root or self.vault, "add", "--", REL)

    def commit(self, root=None):
        git(root or self.vault, "commit", "-q", "-m", "Hermes: add %s weekly edition" % SLUG)

    def push(self, root=None):
        git(root or self.vault, "push", "-q", "origin", "main")

    def land(self, **changes):
        self.write_bundle(**changes)
        self.stage()
        self.commit()
        self.push()

    def verify(self):
        return handoff.verify_vault_bundle(self.vault, REL, "origin/main", SLUG, URL, self.paths)


class VaultBundleGateTests(VaultFixture):
    def test_the_fixture_reproduces_the_false_whitespace_report(self):
        # Probe check: if Git stopped flagging this PDF, the incident shape is not being exercised.
        self.write_bundle()
        self.stage()
        check = subprocess.run(
            ["git", "-C", str(self.vault), "diff", "--cached", "--check"], capture_output=True, text=True
        )
        self.assertNotEqual(check.returncode, 0)
        self.assertIn("trailing whitespace", check.stdout)

    def test_passes_and_names_the_commit_when_bundle_is_pushed_byte_exact(self):
        self.land()
        self.assertEqual(self.verify(), git(self.vault, "rev-parse", "--short", "origin/main"))

    def test_incident_shape_staged_but_never_committed_fails(self):
        self.write_bundle()
        self.stage()
        with self.assertRaisesRegex(handoff.HandoffError, r"carousel\.pdf is missing from the vault"):
            self.verify()

    def test_files_on_disk_but_never_staged_fail(self):
        self.write_bundle()
        with self.assertRaisesRegex(handoff.HandoffError, "is missing from the vault"):
            self.verify()

    def test_committed_but_never_pushed_fails(self):
        self.write_bundle()
        self.stage()
        self.commit()
        with self.assertRaisesRegex(handoff.HandoffError, "is missing from the vault"):
            self.verify()

    def test_bundle_pushed_from_another_clone_is_seen_because_the_gate_fetches(self):
        other = self.base / "other-device"
        subprocess.run(["git", "clone", "-q", str(self.remote), str(other)], check=True, env=GIT_ENV,
                       capture_output=True)
        self.write_bundle(root=other)
        self.stage(root=other)
        self.commit(root=other)
        self.push(root=other)
        stale = subprocess.run(
            ["git", "-C", str(self.vault), "cat-file", "-e", "origin/main:%s/%s-carousel.pdf" % (REL, SLUG)],
            capture_output=True,
        )
        self.assertNotEqual(stale.returncode, 0, "precondition: this vault must not have fetched yet")
        self.verify()

    def test_pdf_differing_from_the_reviewed_artifact_fails(self):
        self.land(pdf=PDF + b"%regenerated with a new CreationDate\n")
        with self.assertRaisesRegex(handoff.HandoffError, "PDF differs from the reviewed artifact"):
            self.verify()

    def test_linkedin_copy_differing_from_the_reviewed_artifact_fails(self):
        self.land(copy=LINKEDIN.replace(b"dropped", b"landed"))
        with self.assertRaisesRegex(handoff.HandoffError, "LinkedIn copy differs"):
            self.verify()

    def test_companion_without_the_published_url_fails(self):
        self.land(edition=EDITION.replace(URL.encode(), b"https://example.invalid/"))
        with self.assertRaisesRegex(handoff.HandoffError, "lacks its edition slug or published URL"):
            self.verify()

    def test_companion_for_a_different_edition_fails(self):
        self.land(edition=EDITION.replace(b"edition: 2026-W48", b"edition: 2026-W47"))
        with self.assertRaisesRegex(handoff.HandoffError, "lacks its edition slug or published URL"):
            self.verify()

    def test_index_without_the_edition_entry_fails(self):
        self.land(entry=b"")
        with self.assertRaisesRegex(handoff.HandoffError, "exactly once"):
            self.verify()

    def test_index_with_a_duplicate_edition_entry_fails(self):
        self.land(entry=ENTRY + ENTRY)
        with self.assertRaisesRegex(handoff.HandoffError, "exactly once"):
            self.verify()

    def test_unreachable_remote_fails_closed(self):
        self.land()
        git(self.vault, "remote", "set-url", "origin", str(self.base / "does-not-exist.git"))
        with self.assertRaisesRegex(handoff.HandoffError, "vault git fetch failed"):
            self.verify()

    def test_missing_vault_directory_fails(self):
        with self.assertRaisesRegex(handoff.HandoffError, "vault directory is unavailable"):
            handoff.verify_vault_bundle(self.base / "nope", REL, "origin/main", SLUG, URL, self.paths)

    def test_option_shaped_ref_is_rejected_before_any_git_call(self):
        sentinel = self.base / "pwned"
        for ref in ("--output=%s" % sentinel, "-x", "", "origin/main:other", "origin main"):
            with self.subTest(ref=ref):
                with self.assertRaisesRegex(handoff.HandoffError, "plain branch ref"):
                    handoff.verify_vault_bundle(self.vault, REL, ref, SLUG, URL, self.paths)
        self.assertFalse(sentinel.exists())


class HandoffOrderingTests(VaultFixture):
    """main() must run the gate after import, on replays, and only when a vault is configured."""

    def setUp(self):
        super().setUp()
        self.review = self.base / "review"
        self.review.mkdir()
        self.workspace = self.base / "workspace"
        self.source_dir = self.base / "weekly"
        self.source_dir.mkdir()
        (self.source_dir / (SLUG + ".md")).write_text("weekly source", encoding="utf-8")
        self.handoff_file = self.base / "handoff.json"
        self.handoff_file.write_text(json.dumps({
            "status": "OK", "slug": SLUG, "url": URL,
            "written_at": datetime.now(timezone.utc).isoformat(), "detail": "built",
        }), encoding="utf-8")
        self.events = []

    def argv(self, vault=True):
        argv = [
            "--handoff", str(self.handoff_file), "--work-dir", str(self.work),
            "--review-root", str(self.review), "--workspace", str(self.workspace),
            "--source-dir", str(self.source_dir), "--producer-cwd", str(self.base),
            "--python", sys.executable, "--worker", "unused-worker",
        ]
        return argv + (["--vault-dir", str(self.vault)] if vault else [])

    def fake_worker(self, args, handoff_data, source):
        self.events.append("worker")
        for platform in ("bluesky", "x"):
            (self.work / ("%s-%s.txt" % (SLUG, platform))).write_bytes(("Concrete fact. %s\n" % URL).encode())

    def fake_producer(self, args, handoff_data, paths):
        self.events.append("producer")
        return {"id": "aigregator-%s-v1" % SLUG, "imported": True}

    def fake_readback(self, review_root, packet_id, paths, slug):
        self.events.append("readback")
        return 3, 0

    def run_main(self, replay=False):
        out, err = io.StringIO(), io.StringIO()
        patches = [mock.patch.object(handoff, "run_worker", self.fake_worker),
                   mock.patch.object(handoff, "run_producer", self.fake_producer),
                   mock.patch.object(handoff, "readback", self.fake_readback)]
        if replay:
            patches.append(mock.patch.object(
                handoff, "existing_packet",
                return_value={"id": "aigregator-%s-v1" % SLUG, "imported": False, "cards": 3, "jobs": 0},
            ))
        with contextlib.ExitStack() as stack:
            for patch in patches:
                stack.enter_context(patch)
            stack.enter_context(contextlib.redirect_stdout(out))
            stack.enter_context(contextlib.redirect_stderr(err))
            code = handoff.main(self.argv(vault=self.use_vault))
        return code, out.getvalue(), err.getvalue()

    use_vault = True

    def test_unsynced_vault_fails_the_run_and_says_cards_were_already_imported(self):
        self.write_bundle()
        self.stage()
        code, out, err = self.run_main()
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("review cards were imported, but the vault bundle is not verified on origin/main", err)
        self.assertEqual(self.events, ["worker", "producer", "readback"])

    def test_synced_vault_reports_the_verified_commit(self):
        self.land()
        code, out, err = self.run_main()
        self.assertEqual(code, 0, err)
        report = json.loads(out)
        self.assertEqual(report["vault"], git(self.vault, "rev-parse", "--short", "origin/main"))
        self.assertEqual((report["cards"], report["jobs"], report["imported"]), (3, 0, True))

    def test_replay_skips_the_worker_but_still_runs_the_gate(self):
        self.write_bundle()
        self.stage()
        code, out, err = self.run_main(replay=True)
        self.assertEqual(code, 1)
        self.assertNotIn("worker", self.events)
        self.assertIn("the vault bundle is not verified", err)
        self.assertNotIn("review cards were imported", err)

    def test_replay_passes_once_the_bundle_lands(self):
        self.land()
        code, out, err = self.run_main(replay=True)
        self.assertEqual(code, 0, err)
        self.assertFalse(json.loads(out)["imported"])
        self.assertIn("vault", json.loads(out))

    def test_without_a_vault_dir_the_gate_is_skipped_for_backward_compatibility(self):
        self.use_vault = False
        code, out, err = self.run_main()
        self.assertEqual(code, 0, err)
        self.assertNotIn("vault", json.loads(out))


if __name__ == "__main__":
    unittest.main()
