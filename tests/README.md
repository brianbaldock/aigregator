# Running the tests

The portable validation suite uses only the pinned packages in `requirements-validation.txt`:

```sh
python -m unittest discover -s tests -v
```

`test_simplepost_weekly_handoff.py` also contains real cross-project integration tests. They use a separate SimplePost checkout, defaulting to `~/projects/simplepost`. If that optional directory is absent, only the tests that invoke the real producer are explicitly skipped. The handoff's local worker, timeout, malformed-input and wrapper checks still run.

To require the full integration coverage and select its checkout:

```sh
AIG_SIMPLEPOST_TEST_ROOT=/path/to/simplepost python -m unittest discover -s tests -v
```

An explicitly configured missing or invalid directory is a test failure, not a skip. An existing checkout whose producer is broken also fails its integration tests. The tests use temporary review stores and stub workers; they do not invoke the live social-publishing job.

The hosted GitHub runner does not have the separate SimplePost checkout. Report its visible skips separately from the full local integration result. Do not describe a hosted run as having exercised SimplePost integration.
