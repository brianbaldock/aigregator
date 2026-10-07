"""End-to-end controls for the staged no_agent daily wrapper."""
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest

import test_digest_contract as fixture
import test_publication_checks as provenance_fixture

REPO = Path(__file__).resolve().parents[1]


class SnapshotHandler(BaseHTTPRequestHandler):
    payloads = {}

    def do_GET(self):
        body = self.payloads.get(self.path)
        if body is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class DailyWrapperTests(unittest.TestCase):
    def setUp(self):
        SnapshotHandler.payloads = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), SnapshotHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()

    def tearDown(self):
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def _render(self, repo, run, edition, items, curation):
        (run / "digest_items.json").write_text(json.dumps(items))
        (run / "curation.json").write_text(json.dumps(curation))
        output = repo / "digests" / f"{edition}.md"
        result = subprocess.run(
            [sys.executable, str(repo / "scripts" / "write_digest.py"), "--items", str(run / "digest_items.json"),
             "--curation", str(run / "curation.json"), "--date", edition, "--digests-dir", str(repo / "digests"),
             "--out", str(output)],
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def _fixture(self, root):
        repo = root / "repo"
        shutil.copytree(REPO / "scripts", repo / "scripts", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copytree(REPO / "templates", repo / "templates")
        shutil.copytree(REPO / "tools", repo / "tools")
        shutil.copytree(REPO / "docs" / "assets", repo / "docs" / "assets")
        (repo / "digests").mkdir()
        run = root / "run"
        run.mkdir()
        now = datetime.now(timezone.utc)
        edition = now.date().isoformat()
        provenance_fixture.PublicationChecksTests().fixture(run)
        item = fixture.news_item(published=now.isoformat())
        items, curation = [item], fixture.curation_for([item])
        (run / "rss_items.json").write_text(json.dumps(items))
        manifest_path = run / "gather_manifest.json"
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest.values():
            entry["collected_at"] = now.isoformat()
        manifest["rss"]["outputs"][0]["sha256"] = hashlib.sha256((run / "rss_items.json").read_bytes()).hexdigest()
        manifest_path.write_text(json.dumps(manifest))
        self._render(repo, run, edition, items, curation)
        build = repo / "scripts" / "build.py"
        original = build.read_text()
        marker = '\nif __name__ == "__main__":'
        self.assertEqual(original.count(marker), 1)
        origin = f"http://127.0.0.1:{self.server.server_port}"
        modified = original.replace('SITE_URL = "https://aigregator.news"', f'SITE_URL = "{origin}"', 1)
        modified = modified.replace(marker, marker + "\n    validate_links_live = lambda *a, **k: []\n    validate_bluesky_urls = lambda *a, **k: []", 1)
        self.assertNotEqual(modified, original)
        build.write_text(modified)
        built = subprocess.run([sys.executable, str(build)], cwd=repo, text=True, capture_output=True)
        self.assertEqual(built.returncode, 0, built.stderr)
        for route, relative in (
            ("/", "index.html"), (f"/digests/{edition}.html", f"digests/{edition}.html"),
            ("/feed.xml", "feed.xml"), ("/atom.xml", "atom.xml"), ("/archive.json", "archive.json"),
        ):
            SnapshotHandler.payloads[route] = (repo / "docs" / relative).read_bytes()
        fakebin = root / "bin"
        fakebin.mkdir()
        (fakebin / "git").write_text("#!/bin/sh\ncase \"$*\" in 'status --porcelain') ;; esac\n")
        (fakebin / "copilot").write_text("#!/bin/sh\necho 'STATUS: OK published by test'\n")
        for name in ("git", "copilot"):
            (fakebin / name).chmod(0o700)
        env = {**os.environ, "AIG_REPO": str(repo), "AIG_LOG": str(root / "wrapper.log"),
               "AIG_PYTHON": sys.executable, "AIG_RUN_DIR": str(run), "AIG_COPILOT": str(fakebin / "copilot"),
               "PATH": str(fakebin) + os.pathsep + os.environ["PATH"]}
        return repo, run, edition, items, curation, env

    def test_real_validators_allow_current_matching_publication(self):
        with tempfile.TemporaryDirectory() as td:
            repo, run, edition, items, curation, env = self._fixture(Path(td))
            result = subprocess.run(["bash", str(repo / "scripts" / "aigregator_digest.sh")],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("updated", result.stdout)
            self.assertIn("aigregator.news", result.stdout)
            self.assertNotIn("verified", result.stdout)
            self.assertIn("verified 5/5", Path(env["AIG_LOG"]).read_text())

    def test_new_markdown_with_stale_docs_fails(self):
        with tempfile.TemporaryDirectory() as td:
            repo, run, edition, items, curation, env = self._fixture(Path(td))
            curation["subtitle"] = "A changed validated artifact must rebuild docs."
            self._render(repo, run, edition, items, curation)
            result = subprocess.run(["bash", str(repo / "scripts" / "aigregator_digest.sh")],
                                    env=env, text=True, capture_output=True)
            self.assertIn("FAIL", result.stdout)
            self.assertNotIn("updated", result.stdout)
            self.assertIn("daily/homepage content differs", Path(env["AIG_LOG"]).read_text())

    def test_fresh_local_digest_and_explicit_model_failure_stay_failed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / "repo"
            (repo / "scripts").mkdir(parents=True)
            (repo / "digests").mkdir()
            shutil.copy(REPO / "scripts" / "aigregator_digest.sh", repo / "scripts")
            (repo / "scripts" / "copilot_digest_brief.md").write_text("brief")
            edition = datetime.now(timezone.utc).date().isoformat()
            (repo / "digests" / f"{edition}.md").write_text("fresh enough without a size rule")
            fakebin = root / "bin"
            fakebin.mkdir()
            (fakebin / "git").write_text("#!/bin/sh\ncase \"$*\" in 'status --porcelain') ;; esac\n")
            (fakebin / "copilot").write_text("#!/bin/sh\necho 'STATUS: FAIL model error'\nexit 1\n")
            for command in ("git", "copilot"):
                (fakebin / command).chmod(0o700)
            result = subprocess.run(
                ["bash", str(repo / "scripts" / "aigregator_digest.sh")],
                env={**os.environ, "AIG_REPO": str(repo), "AIG_LOG": str(root / "log"),
                     "AIG_COPILOT": str(fakebin / "copilot"), "PATH": str(fakebin) + os.pathsep + os.environ["PATH"]},
                text=True, capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("FAIL", result.stdout)
            self.assertNotIn("updated", result.stdout)
            self.assertNotIn("live.", result.stdout)


if __name__ == "__main__":
    unittest.main()
