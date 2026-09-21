import json
import importlib.util
import os
import signal
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
HELPER = REPO / "scripts" / "simplepost_weekly_handoff.py"
SIMPLEPOST = Path("/home/brian/projects/simplepost")
WRAPPER = REPO / "scripts" / "aigregator_weekly_social.sh"


class WeeklyHandoffTests(unittest.TestCase):
    def test_wrapper_uses_validated_copilot_credit_flag(self):
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn("--worker-arg=--max-ai-credits", wrapper)
        self.assertNotIn("--worker-arg=--max-credits", wrapper)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.work = self.base / "work"
        self.work.mkdir()
        self.workspace = self.base / "workspace"
        self.producer_cwd = SIMPLEPOST
        self.source = self.base / "weekly"
        self.source.mkdir()
        self.review = self.base / "review"
        self.output = self.base / "packet.json"
        self.handoff = self.base / "handoff.json"
        self.worker = self.base / "worker.py"
        self.worker.write_text(
            """\
import os
from pathlib import Path
work = Path(os.environ["AIG_WEEKLY_WORK_DIR"])
slug = os.environ["AIG_WEEKLY_SLUG"]
url = os.environ["AIG_WEEKLY_URL"]
for platform, text in {
    "linkedin": f"Latest AI Weekly Roundup just dropped → {url}\\n",
    "bluesky": f"Concrete weekly fact. {url}\\n",
    "x": f"Another concrete weekly fact. {url}\\n",
}.items():
    (work / f"{slug}-{platform}.txt").write_text(text)
(work / f"{slug}-carousel.pdf").write_bytes(b"%PDF-1.4\\nfixture\\n")
""",
            encoding="utf-8",
        )
        self.write_handoff()
        self.write_source()

    def tearDown(self):
        self.temp.cleanup()

    def write_handoff(self, **changes):
        values = {
            "status": "OK",
            "slug": "2026-W39",
            "url": "https://aigregator.news/weekly/2026-W39.html",
            "written_at": datetime.now(timezone.utc).isoformat(),
            "detail": "built",
        }
        values.update(changes)
        self.handoff.write_text(json.dumps(values), encoding="utf-8")

    def write_source(self, slug="2026-W39", content="weekly source"):
        (self.source / (slug + ".md")).write_text(content, encoding="utf-8")

    def invoke(self, *extra):
        return subprocess.run(
            [
                sys.executable, str(HELPER), "--handoff", str(self.handoff),
                "--work-dir", str(self.work), "--review-root", str(self.review),
                "--workspace", str(self.workspace), "--source-dir", str(self.source),
                "--producer-cwd", str(self.producer_cwd),
                "--python", sys.executable, "--worker", sys.executable,
                "--worker-arg", str(self.worker), *extra,
            ],
            cwd=REPO, text=True, capture_output=True,
        )

    def test_imports_exact_pdf_title_copy_and_reports_no_jobs(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["id"], "aigregator-2026-W39-v1")
        self.assertTrue(report["imported"])
        self.assertEqual(report["cards"], 3)
        self.assertEqual(report["jobs"], 0)
        packet = json.loads((self.workspace / "2026-W39.json").read_text())
        self.assertEqual(packet["attachments"]["linkedin"][0]["title"], "AI Weekly Roundup | 2026-W39")
        self.assertEqual(packet["posts"]["linkedin"], "Latest AI Weekly Roundup just dropped → https://aigregator.news/weekly/2026-W39.html\n")
        self.assertTrue((self.workspace / "2026-W39.json").exists())

    def test_wrapper_uses_live_simplepost_root_and_private_workspace(self):
        wrapper = WRAPPER.read_text(encoding="utf-8")
        self.assertIn('REVIEW_ROOT="/home/brian/.local/share/simplepost"', wrapper)
        self.assertIn('WORKSPACE="/home/brian/.local/share/simplepost/weekly-producer"', wrapper)
        self.assertNotIn("weekly-review", wrapper)

    def test_two_editions_share_workspace_without_packet_conflict(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.write_handoff(slug="2026-W40", url="https://aigregator.news/weekly/2026-W40.html")
        self.write_source("2026-W40")
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertNotEqual(json.loads(first.stdout)["id"], json.loads(second.stdout)["id"])
        self.assertTrue((self.workspace / "2026-W39.json").exists())
        self.assertTrue((self.workspace / "2026-W40.json").exists())

    def test_existing_approved_packet_is_held_before_worker_runs(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        with sqlite3.connect(self.review / "state.sqlite3") as db:
            db.execute("UPDATE cards SET state='ready' WHERE packet_id='aigregator-2026-W39-v1'")
        self.worker.write_text("raise SystemExit(99)\n", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manual reconciliation", result.stderr)

    def test_copy_readback_preserves_crlf_bytes(self):
        self.worker.write_text(
            """\
import os
from pathlib import Path
work = Path(os.environ["AIG_WEEKLY_WORK_DIR"])
slug = os.environ["AIG_WEEKLY_SLUG"]
url = os.environ["AIG_WEEKLY_URL"]
(work / f"{slug}-linkedin.txt").write_bytes(f"Latest AI Weekly Roundup just dropped → {url}\\n".encode())
(work / f"{slug}-bluesky.txt").write_bytes(f"Concrete fact. {url}\\r\\n".encode())
(work / f"{slug}-x.txt").write_bytes(f"Another fact. {url}\\n".encode())
(work / f"{slug}-carousel.pdf").write_bytes(b"%PDF-1.4\\nfixture\\n")
""",
            encoding="utf-8",
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        packet = json.loads((self.workspace / "2026-W39.json").read_text())
        self.assertTrue(packet["posts"]["bluesky"].endswith("\r\n"))

    def test_tampered_stored_pdf_asset_fails_byte_readback(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        with sqlite3.connect(self.review / "state.sqlite3") as db:
            asset = Path(db.execute(
                "SELECT document_path FROM cards WHERE packet_id=? AND platform='linkedin'",
                ("aigregator-2026-W39-v1",),
            ).fetchone()[0])
        asset.write_bytes(b"%PDF-1.4\ntampered\n")
        spec = importlib.util.spec_from_file_location("weekly_handoff", HELPER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with self.assertRaisesRegex(module.HandoffError, "stored PDF bytes"):
            module.readback(self.review, "aigregator-2026-W39-v1", module.artifact_paths(self.work, "2026-W39"), "2026-W39")

    def test_worker_timeout_kills_its_process_group(self):
        pid_file = self.base / "child.pid"
        self.worker.write_text(
            "import os, subprocess, sys, time\n"
            "from pathlib import Path\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "Path(%r).write_text(str(child.pid))\n"
            "time.sleep(30)\n" % str(pid_file),
            encoding="utf-8",
        )
        result = self.invoke("--worker-timeout", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("worker timed out", result.stderr)
        pid = int(pid_file.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_producer_timeout_kills_its_process_group(self):
        producer = self.base / "fake-producer" / "simplepost"
        producer.mkdir(parents=True)
        (producer / "__init__.py").write_text("", encoding="utf-8")
        pid_file = self.base / "producer-child.pid"
        (producer / "producer.py").write_text(
            "import subprocess, sys, time\nfrom pathlib import Path\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "Path(%r).write_text(str(child.pid))\ntime.sleep(30)\n" % str(pid_file),
            encoding="utf-8",
        )
        self.producer_cwd = producer.parent
        result = self.invoke("--producer-timeout", "1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("producer timed out", result.stderr)
        pid = int(pid_file.read_text())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_rejects_stale_future_and_malformed_handoffs(self):
        for values in (
            {"written_at": (datetime.now(timezone.utc) - timedelta(hours=13)).isoformat()},
            {"written_at": (datetime.now(timezone.utc) + timedelta(minutes=1)).isoformat()},
            {"slug": "../2026-W39"},
        ):
            with self.subTest(values=values):
                self.write_handoff(**values)
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.output.exists())

    def test_fails_when_worker_lies_with_success_without_artifacts(self):
        self.worker.write_text("pass\n", encoding="utf-8")
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required artifact", result.stderr)

    def test_fails_on_nonzero_worker_and_preserves_partial_artifacts(self):
        self.worker.write_text(
            "from pathlib import Path\nimport os\n"
            "Path(os.environ['AIG_WEEKLY_WORK_DIR'], 'partial.txt').write_text('keep')\n"
            "raise SystemExit(7)\n",
            encoding="utf-8",
        )
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.work / "partial.txt").exists())
        self.assertIn("worker exited 7", result.stderr)

    def test_replay_is_idempotent_and_skips_worker_when_artifacts_complete(self):
        first = self.invoke()
        self.assertEqual(first.returncode, 0, first.stderr)
        self.worker.write_text("raise SystemExit(99)\n", encoding="utf-8")
        second = self.invoke()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertFalse(json.loads(second.stdout)["imported"])

    def test_rejects_legacy_weekly_edition_after_candidate_is_prepared(self):
        self.work.mkdir(exist_ok=True)
        legacy = self.base / "legacy"
        legacy.mkdir()
        for platform in ("x", "bluesky", "linkedin"):
            (legacy / (platform + ".txt")).write_text(
                "https://aigregator.news/weekly/2026-W39.html", encoding="utf-8"
            )
        subprocess.run(
            [sys.executable, "-m", "simplepost.producer", "--packet-id", "legacy-W38",
             "--x", str(legacy / "x.txt"), "--bluesky", str(legacy / "bluesky.txt"),
             "--linkedin", str(legacy / "linkedin.txt"), "--root", str(self.review)],
            cwd=SIMPLEPOST, check=True, text=True, capture_output=True,
        )
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already represented", result.stderr)


if __name__ == "__main__":
    unittest.main()
