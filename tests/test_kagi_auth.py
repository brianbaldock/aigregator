"""Exercise the v1 auth contract and preserve legacy v0 auth without network calls."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest import mock


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / filename)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


kagi = load_script("aigregator_kagi_helper", "kagi.py")
health = load_script("aigregator_kagi_health", "kagi_health.py")
TEST_TOKEN = "test-token-not-a-real-secret"


def response(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


class KagiAuthenticationTests(unittest.TestCase):
    def test_v1_search_sends_bearer_and_returns_results(self):
        payload = {"data": {"search": [{"title": "Result", "url": "https://example.com/"}]}}
        output = io.StringIO()
        with mock.patch.object(kagi, "load_token", return_value=TEST_TOKEN), \
             mock.patch.object(kagi.urllib.request, "urlopen", return_value=response(payload)) as urlopen, \
             contextlib.redirect_stdout(output):
            kagi.cmd_search("microsoft", 1, 2)
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://kagi.com/api/v1/search")
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.get_header("Authorization"), f"Bearer {TEST_TOKEN}")
        self.assertEqual(json.loads(req.data), {"query": "microsoft", "limit": 1})
        self.assertEqual(len(json.loads(output.getvalue())["data"]["search"]), 1)

    def test_v1_extract_sends_bearer(self):
        payload = {"data": [{"url": "https://example.com/", "markdown": "Example"}]}
        output = io.StringIO()
        with mock.patch.object(kagi, "load_token", return_value=TEST_TOKEN), \
             mock.patch.object(kagi.urllib.request, "urlopen", return_value=response(payload)) as urlopen, \
             contextlib.redirect_stdout(output):
            kagi.cmd_extract(["https://example.com/"])
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://kagi.com/api/v1/extract")
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.get_header("Authorization"), f"Bearer {TEST_TOKEN}")
        self.assertEqual(json.loads(req.data), {"pages": [{"url": "https://example.com/"}]})
        self.assertEqual(json.loads(output.getvalue()), payload)

    def test_health_probe_sends_bearer_and_counts_results(self):
        payload = {"data": {"search": [{"title": "Result", "url": "https://example.com/"}]}}
        with mock.patch.object(health.urllib.request, "urlopen", return_value=response(payload)) as urlopen:
            result = health.search(TEST_TOKEN, "microsoft")
        req = urlopen.call_args.args[0]
        self.assertEqual(req.full_url, "https://kagi.com/api/v1/search")
        self.assertEqual(req.method, "POST")
        self.assertEqual(req.get_header("Authorization"), f"Bearer {TEST_TOKEN}")
        self.assertEqual(json.loads(req.data), {"query": "microsoft", "limit": 10})
        self.assertTrue(result["ok"])
        self.assertEqual(health.fresh_count(result), 1)

    def test_legacy_v0_summarizer_keeps_bot_header(self):
        payload = {"data": {"output": "Summary"}}
        with mock.patch.object(kagi, "load_token", return_value=TEST_TOKEN), \
             mock.patch.object(kagi.urllib.request, "urlopen", return_value=response(payload)) as urlopen:
            result = kagi._get(kagi.BASE_V0, "/summarize", {"url": "https://example.com/"}, "KAGI_API_TOKEN")
        req = urlopen.call_args.args[0]
        self.assertEqual(req.get_header("Authorization"), f"Bot {TEST_TOKEN}")
        self.assertEqual(result, payload)


if __name__ == "__main__":
    unittest.main()
