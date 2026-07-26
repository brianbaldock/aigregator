#!/usr/bin/env bash
# Exercise verify_h2_failures.py against synthetic lychee reports.
set -uo pipefail
cd "$(dirname "$0")"
V=../scripts/verify_h2_failures.py
pass=0; fail=0
check() { # name expected_exit file
  python3 "$V" "$3" >/tmp/h2test.out 2>&1; got=$?
  if [ "$got" = "$2" ]; then echo "PASS $1 (exit $got)"; pass=$((pass+1));
  else echo "FAIL $1 (want $2 got $got)"; sed 's/^/     /' /tmp/h2test.out; fail=$((fail+1)); fi
}

mk() { printf '%s' "$2" > "/tmp/h2_$1.json"; }

mk clean '{"error_map":{}}'
mk h2ok '{"error_map":{"digests/a.md":[{"url":"https://www.npr.org/2026/07/17/nx-s1-5898504/ice-medicaid-palantir-data","status":{"text":"HTTP/2 protocol error. Server may not support HTTP/2 properly"}}]}}'
mk h2dead '{"error_map":{"digests/a.md":[{"url":"https://www.npr.org/this-page-does-not-exist-abcxyz","status":{"text":"HTTP/2 protocol error. Server may not support HTTP/2 properly"}}]}}'
mk real404 '{"error_map":{"digests/a.md":[{"url":"https://www.npr.org/this-page-does-not-exist-abcxyz","status":{"text":"Rejected status code: 404 Not Found","code":404}}]}}'
mk mixed '{"error_map":{"digests/a.md":[{"url":"https://www.npr.org/2026/07/17/nx-s1-5898504/ice-medicaid-palantir-data","status":{"text":"HTTP/2 protocol error"}},{"url":"https://example.com/nope","status":{"text":"Rejected status code: 404 Not Found","code":404}}]}}'
mk dup '{"error_map":{"digests/a.md":[{"url":"https://www.npr.org/2026/07/17/nx-s1-5898504/ice-medicaid-palantir-data","status":{"text":"HTTP/2 protocol error"}}],"digests/b.md":[{"url":"https://www.npr.org/2026/07/17/nx-s1-5898504/ice-medicaid-palantir-data","status":{"text":"HTTP/2 protocol error"}}]}}'
# Real CI shape: first occurrence has the h2 text, the repeat is bare "Error (cached)".
mk cached '{"error_map":{"digests/a.md":[{"url":"https://www.npr.org/2026/07/17/nx-s1-5898504/ice-medicaid-palantir-data","status":{"text":"HTTP/2 protocol error. Server may not support HTTP/2 properly"}},{"url":"https://www.npr.org/2026/07/17/nx-s1-5898504/ice-medicaid-palantir-data","status":{"text":"Error (cached)"}}]}}'
# A cached entry whose URL has NO h2 evidence anywhere must still fail.
mk cachedreal '{"error_map":{"digests/a.md":[{"url":"https://example.com/nope","status":{"text":"Error (cached)"}}]}}'
printf 'not json' > /tmp/h2_corrupt.json

check "clean report -> pass"            0 /tmp/h2_clean.json
check "h2 error, live URL -> pass"      0 /tmp/h2_h2ok.json
check "h2 error, dead URL -> fail"      1 /tmp/h2_h2dead.json
check "real 404 -> fail"                1 /tmp/h2_real404.json
check "mixed h2+404 -> fail"            1 /tmp/h2_mixed.json
check "dup url across files -> pass"    0 /tmp/h2_dup.json
check "h2 + cached repeat -> pass"      0 /tmp/h2_cached.json
check "cached, no h2 evidence -> fail"  1 /tmp/h2_cachedreal.json
check "corrupt report -> fail closed"   1 /tmp/h2_corrupt.json
check "missing report -> fail closed"   1 /tmp/h2_nonexistent.json

echo "---"; echo "passed=$pass failed=$fail"; [ "$fail" = 0 ]
