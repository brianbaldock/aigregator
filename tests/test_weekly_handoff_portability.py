"""Keep portable handoff checks independent of the optional sibling project."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import test_simplepost_weekly_handoff as handoff


class WeeklyHandoffPortabilityTests(unittest.TestCase):
    def run_case_without_checkout(self, name, *, configured=False):
        with tempfile.TemporaryDirectory() as directory:
            absent = Path(directory) / "missing-simplepost"
            self.assertFalse(absent.exists())
            with mock.patch.object(handoff, "SIMPLEPOST", absent), mock.patch.dict(os.environ):
                os.environ.pop("AIG_SIMPLEPOST_TEST_ROOT", None)
                if configured:
                    os.environ["AIG_SIMPLEPOST_TEST_ROOT"] = str(absent)
                result = unittest.TestResult()
                handoff.WeeklyHandoffTests(name).run(result)
            self.assertEqual(result.testsRun, 1)
            return result

    def test_worker_failure_check_runs_without_simplepost(self):
        result = self.run_case_without_checkout("test_fails_when_worker_lies_with_success_without_artifacts")
        self.assertEqual(result.skipped, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])

    def test_missing_optional_checkout_is_reported_as_skip(self):
        result = self.run_case_without_checkout("test_imports_exact_pdf_title_copy_and_reports_no_jobs")
        self.assertEqual(result.errors, [])
        self.assertEqual(result.failures, [])
        self.assertEqual(len(result.skipped), 1)
        self.assertIn("SimplePost", result.skipped[0][1])

    def test_invalid_explicit_checkout_is_failure_not_skip(self):
        result = self.run_case_without_checkout(
            "test_imports_exact_pdf_title_copy_and_reports_no_jobs", configured=True
        )
        self.assertEqual(result.skipped, [])
        self.assertEqual(result.errors, [])
        self.assertEqual(len(result.failures), 1)
        self.assertIn("AIG_SIMPLEPOST_TEST_ROOT", result.failures[0][1])

    def test_checkout_location_is_configurable(self):
        with tempfile.TemporaryDirectory() as directory:
            expected = Path(directory) / "chosen-simplepost"
            with mock.patch.dict(os.environ, {"AIG_SIMPLEPOST_TEST_ROOT": str(expected)}):
                spec = importlib.util.spec_from_file_location("handoff_config_probe", handoff.__file__)
                assert spec is not None and spec.loader is not None
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
            self.assertEqual(module.SIMPLEPOST, expected)


if __name__ == "__main__":
    unittest.main()
