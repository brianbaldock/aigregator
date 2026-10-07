"""HTTP controls for publication byte-for-byte verification."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
import build
import verify_publication


class PublicationHandler(BaseHTTPRequestHandler):
    payloads = {}
    sequences = {}
    requests = {}

    def do_GET(self):
        self.requests[self.path] = self.requests.get(self.path, 0) + 1
        sequence = self.sequences.get(self.path, [])
        body = sequence.pop(0) if sequence else self.payloads.get(self.path)
        if body is None:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_):
        pass


class VerifyPublicationTests(unittest.TestCase):
    def setUp(self):
        PublicationHandler.payloads = {}
        PublicationHandler.sequences = {}
        PublicationHandler.requests = {}
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), PublicationHandler)
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.previous_site_url = build.SITE_URL
        build.SITE_URL = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        build.SITE_URL = self.previous_site_url
        self.server.shutdown()
        self.thread.join()
        self.server.server_close()

    def fixture(self, root):
        docs = Path(root)
        edition = "2026-10-06"
        files = {
            "index.html": b"home",
            f"digests/{edition}.html": b"digest",
            "feed.xml": b"rss",
            "atom.xml": b"atom",
            "archive.json": b'{"digests":[]}',
        }
        for relative, content in files.items():
            path = docs / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            PublicationHandler.payloads["/" if relative == "index.html" else f"/{relative}"] = content
        return docs, edition

    def test_matching_local_server_artifacts_pass(self):
        with tempfile.TemporaryDirectory() as td:
            docs, edition = self.fixture(td)
            rows, failures = verify_publication.verify(docs, edition, timeout=1, retries=1, delay=0)
            self.assertEqual(len(rows), 5)
            self.assertFalse(failures, failures)

    def test_http_200_stale_content_fails(self):
        with tempfile.TemporaryDirectory() as td:
            docs, edition = self.fixture(td)
            PublicationHandler.payloads["/feed.xml"] = b"stale rss"
            rows, failures = verify_publication.verify(docs, edition, timeout=1, retries=2, delay=0)
            self.assertEqual(PublicationHandler.requests["/feed.xml"], 2)
            self.assertEqual(len(rows), 5)
            self.assertTrue(any("/feed.xml" in failure and "differ" in failure for failure in failures), failures)

    def test_stale_bytes_retry_until_propagated(self):
        with tempfile.TemporaryDirectory() as td:
            docs, edition = self.fixture(td)
            PublicationHandler.sequences["/feed.xml"] = [b"stale rss", b"rss"]
            rows, failures = verify_publication.verify(docs, edition, timeout=1, retries=3, delay=0)
            self.assertEqual(PublicationHandler.requests["/feed.xml"], 2)
            self.assertFalse(failures, failures)
            self.assertEqual(sum(row[4] for row in rows), 5)

    def test_empty_local_and_noncanonical_dates_are_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            docs, edition = self.fixture(td)
            (docs / "feed.xml").write_bytes(b"")
            rows, failures = verify_publication.verify(docs, edition, timeout=1, retries=1, delay=0)
            self.assertEqual(len(rows), 4)
            self.assertTrue(any("local artifact is empty" in failure for failure in failures), failures)
            result = subprocess.run(
                [sys.executable, str(REPO / "scripts" / "verify_publication.py"),
                 "--date", "20261006", "--docs", str(docs), "--retries", "1", "--delay", "0"],
                text=True, capture_output=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exactly YYYY-MM-DD", result.stderr)


if __name__ == "__main__":
    unittest.main()
