"""End-to-end health checks for gather's isolated source collection."""
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import time
import unittest

REPO = Path(__file__).resolve().parents[1]
GATHER_PATH = REPO / "scripts" / "gather.py"
LOG = Path("/home/brian/projects/AIgregator-out/validation-implementation/gather-tests.log")


def load_gather():
    spec = importlib.util.spec_from_file_location("gather_under_test", GATHER_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class GatherHealthTests(unittest.TestCase):
    def setUp(self):
        self.collector = load_gather()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "run"
        self.root.mkdir()
        self.stub = Path(self.tmp.name) / "stub.py"

    def tearDown(self):
        self.tmp.cleanup()

    def write_stub(self, body):
        self.stub.write_text(
            "import json, os, pathlib, sys, time\n"
            "root = pathlib.Path(os.environ['AIG_RUN_DIR'])\n" + body
        )

    @contextlib.contextmanager
    def sources(self, name="rss"):
        original = self.collector._sources
        self.collector._sources = lambda _run: [
            (name, [sys.executable, str(self.stub)], {})]
        try:
            yield
        finally:
            self.collector._sources = original

    def gather(self, name="rss"):
        return self.gather_sources([(name, [sys.executable, str(self.stub)], {})])

    def gather_sources(self, sources):
        old_env = os.environ.get("AIG_RUN_DIR")
        old_argv = sys.argv
        original = self.collector._sources
        os.environ["AIG_RUN_DIR"] = str(self.root)
        sys.argv = ["gather.py"]
        self.collector._sources = lambda _run: sources
        try:
            return self.collector.main()
        finally:
            self.collector._sources = original
            sys.argv = old_argv
            if old_env is None:
                os.environ.pop("AIG_RUN_DIR", None)
            else:
                os.environ["AIG_RUN_DIR"] = old_env

    def manifest(self):
        return json.loads((self.root / "gather_manifest.json").read_text())

    def test_positive_fresh_output_has_generation_and_hash_evidence(self):
        self.write_stub(
            "path = root / 'rss_items.json'\n"
            "path.write_text(json.dumps([{'title': 'fresh'}]))\n"
        )
        self.assertEqual(self.gather(), 0)
        entry = self.manifest()["rss"]
        output = self.root / "rss_items.json"
        self.assertEqual(entry["status"], "OK")
        self.assertEqual(entry["count"], 1)
        self.assertTrue(entry["generation_id"])
        self.assertTrue(entry["collected_at"])
        self.assertEqual(entry["outputs"], [{
            "path": "rss_items.json",
            "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        }])

    def test_zero_list_is_empty_not_ok(self):
        self.write_stub("(root / 'rss_items.json').write_text('[]')\n")
        self.assertEqual(self.gather(), 1)
        self.assertEqual(self.manifest()["rss"]["status"], "EMPTY")

    def test_rc_one_cannot_consume_old_data(self):
        self.write_stub(
            "(root / 'rss_items.json').write_text(json.dumps([{'title': 'first'}]))\n"
        )
        self.assertEqual(self.gather(), 0)
        self.write_stub("sys.exit(1)\n")
        self.assertEqual(self.gather(), 1)
        self.assertEqual(self.manifest()["rss"]["status"], "FAIL")
        self.assertFalse((self.root / "rss_items.json").exists())

    def test_rc_zero_without_write_cannot_consume_old_data(self):
        (self.root / "rss_items.json").write_text(json.dumps([{"title": "stale"}]))
        self.write_stub("pass\n")
        self.assertEqual(self.gather(), 1)
        self.assertEqual(self.manifest()["rss"]["status"], "FAIL")
        self.assertFalse((self.root / "rss_items.json").exists())

    def test_malformed_regular_shape_fails(self):
        self.write_stub("(root / 'rss_items.json').write_text(json.dumps({'not': 'a list'}))\n")
        self.assertEqual(self.gather(), 1)
        self.assertEqual(self.manifest()["rss"]["status"], "FAIL")

    def test_all_empty_opensource_is_empty(self):
        self.write_stub(
            "(root / 'opensource.json').write_text(json.dumps({"
            "'github_trending': [], 'github_watchlist': [], 'hf_trending': []}))\n"
        )
        self.assertEqual(self.gather("opensource"), 1)
        self.assertEqual(self.manifest()["opensource"]["status"], "EMPTY")
        self.assertEqual(self.manifest()["opensource"]["count"], 0)

    def test_kagi_stale_leftovers_are_removed_when_new_run_fails(self):
        kagi = self.root / "kagi"
        kagi.mkdir()
        (kagi / "old.json").write_text(json.dumps({"data": {"search": [{"title": "old"}]}}))
        self.write_stub("sys.exit(1)\n")
        self.assertEqual(self.gather("kagi"), 1)
        self.assertEqual(self.manifest()["kagi"]["status"], "FAIL")
        self.assertFalse(list(kagi.glob("*.json")))

    def test_malformed_kagi_data_shapes_fail_without_crashing(self):
        self.write_stub(
            "(root / 'kagi').mkdir()\n"
            "(root / 'kagi' / 'bad.json').write_text(json.dumps({'data': None}))\n"
        )
        self.assertEqual(self.gather("kagi"), 1)
        entry = self.manifest()["kagi"]
        self.assertEqual(entry["status"], "FAIL")
        self.assertEqual(entry["count"], None)
        self.assertEqual(entry["rc"], 0)

    def test_invalid_utf8_source_fails_without_crashing(self):
        self.write_stub("(root / 'rss_items.json').write_bytes(b'\\xff')\n")
        self.assertEqual(self.gather(), 1)
        entry = self.manifest()["rss"]
        self.assertEqual(entry["status"], "FAIL")
        self.assertEqual(entry["count"], None)
        self.assertEqual(entry["rc"], 0)

    def test_nonblocking_lock_refuses_concurrent_gather(self):
        if os.name == "nt":
            self.skipTest("fcntl locking is POSIX-only")
        import fcntl
        lock = open(self.root / ".gather.lock", "w")
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            self.write_stub("pass\n")
            self.assertEqual(self.gather(), 1)
            self.assertFalse((self.root / "gather_manifest.json").exists())
        finally:
            lock.close()

    def test_timeout_removes_old_output(self):
        (self.root / "rss_items.json").write_text(json.dumps([{"title": "stale"}]))
        self.write_stub("time.sleep(2)\n")
        original = self.collector.PER_SOURCE_TIMEOUT
        self.collector.PER_SOURCE_TIMEOUT = 0.01
        try:
            self.assertEqual(self.gather(), 1)
        finally:
            self.collector.PER_SOURCE_TIMEOUT = original
        self.assertEqual(self.manifest()["rss"]["status"], "TIMEOUT")
        self.assertFalse((self.root / "rss_items.json").exists())

    def test_launch_failure_cleans_up_started_child_and_replaces_manifest(self):
        self.write_stub("time.sleep(10)\n")
        prior = {"rss": {"status": "OK", "generation_id": "old"}}
        (self.root / "gather_manifest.json").write_text(json.dumps(prior))
        result = self.gather_sources([
            ("rss", [sys.executable, str(self.stub)], {}),
            ("arxiv", ["/does/not/exist"], {}),
        ])
        self.assertEqual(result, 1)
        manifest = self.manifest()
        self.assertNotEqual(manifest["rss"]["generation_id"], "old")
        self.assertEqual(manifest["rss"]["status"], "FAIL")
        self.assertEqual(manifest["arxiv"]["status"], "FAIL")

    def test_promotion_failure_replaces_prior_manifest_and_cleans_output(self):
        self.write_stub(
            "(root / 'rss_items.json').write_text(json.dumps([{'title': 'fresh'}]))\n"
        )
        (self.root / "rss_items.json").write_text(json.dumps([{"title": "old"}]))
        (self.root / "gather_manifest.json").write_text(
            json.dumps({"rss": {"status": "OK", "generation_id": "old"}})
        )
        original = self.collector._promote
        self.collector._promote = lambda *_args: (_ for _ in ()).throw(OSError("disk unavailable"))
        try:
            self.assertEqual(self.gather(), 1)
        finally:
            self.collector._promote = original
        entry = self.manifest()["rss"]
        self.assertEqual(entry["status"], "FAIL")
        self.assertNotEqual(entry["generation_id"], "old")
        self.assertFalse((self.root / "rss_items.json").exists())

    def test_kill_group_terminates_child_after_leader_exits(self):
        self.write_stub(
            "child = pathlib.Path(os.environ['CHILD_PID'])\n"
            "p = __import__('subprocess').Popen([sys.executable, '-c', "
            "'import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(10)'])\n"
            "child.write_text(str(p.pid))\n"
        )
        child_path = Path(self.tmp.name) / "child-pid"
        old_child = os.environ.get("CHILD_PID")
        os.environ["CHILD_PID"] = str(child_path)
        try:
            proc = self.collector._launch([sys.executable, str(self.stub)], {"AIG_RUN_DIR": str(self.root)})
            for _ in range(50):
                if child_path.exists():
                    break
                time.sleep(0.01)
            self.assertTrue(child_path.exists())
            self.collector._kill_group(proc)
            child_pid = int(child_path.read_text())
            for _ in range(100):
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.01)
            else:
                self.fail("child process survived process-group termination")
        finally:
            if old_child is None:
                os.environ.pop("CHILD_PID", None)
            else:
                os.environ["CHILD_PID"] = old_child

if __name__ == "__main__":
    unittest.main()
