#!/usr/bin/env bash
# Candidate replacement for the deployed social wrapper. It is not installed here.
set -euo pipefail

REPO="/home/brian/projects/AIgregator"
PYTHON="/home/brian/projects/simplepost-out/venv/bin/python"
SIMPLEPOST_ROOT="/home/brian/.local/share/simplepost/releases/current/hermes-plugin"
REVIEW_ROOT="/home/brian/.local/share/simplepost"
HANDOFF="/tmp/aig-weekly-handoff.json"
WORK_DIR="/home/brian/.local/share/simplepost/weekly-producer/artifacts"
WORKSPACE="/home/brian/.local/share/simplepost/weekly-producer"
BRIEF="scripts/copilot_weekly_social_brief.md"
LOG="/tmp/aig-copilot-weekly-simplepost.log"

emit() { printf '%s\n' "$1"; }
fail() { emit "AIgregator weekly SimplePost FAIL: $1"; exit 1; }

[ -d "$REPO" ] || fail "repository unavailable"
[ -d "$SIMPLEPOST_ROOT" ] || fail "SimplePost release unavailable"
[ -x "$PYTHON" ] || fail "configured Python unavailable"
[ -f "$HANDOFF" ] || fail "no weekly handoff file"
mkdir -p "$WORK_DIR" "$WORKSPACE"
chmod 700 "$WORK_DIR" "$WORKSPACE"

"$PYTHON" "$REPO/scripts/simplepost_weekly_handoff.py" \
  --handoff "$HANDOFF" \
  --work-dir "$WORK_DIR" \
  --review-root "$REVIEW_ROOT" \
  --workspace "$WORKSPACE" \
  --source-dir "$REPO/weekly" \
  --producer-cwd "$SIMPLEPOST_ROOT" \
  --python "$PYTHON" \
  --repo-root "$REPO" \
  --worker copilot \
  --worker-arg=-p \
  --worker-arg="Read $BRIEF and execute it exactly. Prepare only the local artifacts specified there; do not invoke SimplePost, Buffer, or social distribution." \
  --worker-arg=--model \
  --worker-arg=gpt-5.6-terra \
  --worker-arg=--reasoning-effort \
  --worker-arg=medium \
  --worker-arg=--max-ai-credits \
  --worker-arg=80 \
  --worker-arg=--no-remote \
  --worker-arg=--no-remote-export \
  --worker-arg=--disable-builtin-mcps \
  --worker-arg=--allow-all-tools \
  --worker-arg=--allow-all-paths \
  --worker-arg=--no-color \
  >"$LOG" 2>&1 || fail "validated producer handoff failed (see $LOG)"

RESULT="$(tail -n 1 "$LOG")"
emit "AIgregator weekly SimplePost review packet imported: $RESULT"
emit "Unapproved Discord review cards only; no Buffer drafts, scheduling, or publishing occurred."
