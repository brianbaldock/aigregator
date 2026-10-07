#!/usr/bin/env bash
# Staged no_agent daily wrapper. This file is not installed by the repository.
set -uo pipefail

REPO="${AIG_REPO:-$HOME/projects/AIgregator}"
LOG="${AIG_LOG:-/tmp/aig-copilot-digest.log}"
BRIEF="scripts/copilot_digest_brief.md"
PYTHON="${AIG_PYTHON:-$REPO/.venv/bin/python}"
COPILOT="${AIG_COPILOT:-copilot}"
TODAY_UTC="$(date -u +%Y-%m-%d)"
DIGEST_URL="https://aigregator.news/digests/${TODAY_UTC}.html"

emit() { printf '%s\n' "$1"; }

cd "$REPO" 2>/dev/null || { emit "FAIL: cannot cd $REPO"; exit 0; }
if ! git checkout main >/dev/null 2>&1 || ! git pull --ff-only origin main >/dev/null 2>&1; then
  emit "FAIL: cannot update main"; exit 0
fi
if [ -n "$(git status --porcelain)" ] || [ ! -f "$BRIEF" ]; then
  emit "FAIL: main is dirty or missing $BRIEF"; exit 0
fi

timeout 3600 "$COPILOT" -p "Read the file scripts/copilot_digest_brief.md in this repository and execute every phase in it exactly as written. End with the single STATUS line it specifies." \
  --model claude-opus-4.8 --effort medium --allow-all-tools --allow-all-paths --no-color >"$LOG" 2>&1
COPILOT_EC=$?
STATUS_MATCHES="$(grep -ac '^STATUS:' "$LOG" 2>/dev/null)" || STATUS_MATCHES=0
STATUS_LINE="$(grep -a '^STATUS:' "$LOG" 2>/dev/null | tail -1)"

if [ "$COPILOT_EC" -ne 0 ] || [ "$STATUS_MATCHES" -ne 1 ] || [[ "$STATUS_LINE" != "STATUS: OK "* ]]; then
  emit "⚠️ **AIgregator FAIL** :: copilot did not report one successful STATUS (exit $COPILOT_EC; see $LOG)"
  exit 0
fi

validation=( "$PYTHON" "$REPO/scripts/validate_digest.py" --date "$TODAY_UTC" --digest "$REPO/digests/${TODAY_UTC}.md" --docs "$REPO/docs" )
if [ -n "${AIG_RUN_DIR:-}" ]; then
  validation+=(--run-dir "$AIG_RUN_DIR")
fi
if ! "${validation[@]}" >>"$LOG" 2>&1; then
  emit "⚠️ **AIgregator FAIL** :: local digest validation failed"
  exit 0
fi
if ! "$PYTHON" "$REPO/scripts/verify_publication.py" --date "$TODAY_UTC" --docs "$REPO/docs" >>"$LOG" 2>&1; then
  emit "⚠️ **AIgregator FAIL** :: published artifacts did not verify"
  exit 0
fi

printf '📰 **AIgregator updated** :: %s\n' "$TODAY_UTC"
printf 'Fresh dispatch is live. %s\n' "$DIGEST_URL"
