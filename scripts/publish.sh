#!/usr/bin/env bash
# Offline-gated publisher with post-push publication verification.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="${AIG_PYTHON:-$REPO/.venv/bin/python}"
DATE="$(date -u +%Y-%m-%d)"
RUN_DIR=""
DRY_RUN=0
HISTORICAL=0

while (($#)); do
  case "$1" in
    --dry-run) DRY_RUN=1 ;;
    --historical-replay) HISTORICAL=1 ;;
    --run-dir) RUN_DIR="$2"; shift ;;
    --run-dir=*) RUN_DIR="${1#*=}" ;;
    --*) echo "unknown option: $1" >&2; exit 2 ;;
    *) DATE="$1" ;;
  esac
  shift
done
if ((HISTORICAL && !DRY_RUN)); then
  echo "--historical-replay is allowed only with --dry-run" >&2
  exit 2
fi
cd "$REPO"
[[ "$("$PYTHON" -c 'import sys; print(sys.executable)' 2>/dev/null)" ]] || {
  echo "Python interpreter is unavailable: $PYTHON" >&2; exit 1; }
if ((!DRY_RUN)); then
  [[ "$(git branch --show-current)" == "main" ]] || { echo "publication requires main" >&2; exit 1; }
fi

if ((!DRY_RUN)); then
  # A publisher must not absorb unrelated work. The named digest is the sole
  # permitted pre-existing change; docs are generated only after validation.
  while IFS= read -r changed; do
    path="${changed:3}"
    [[ "$path" == "digests/$DATE.md" ]] || { echo "unrelated source change: $path" >&2; exit 1; }
  done < <(git status --porcelain)
fi

gate=( "$PYTHON" "$REPO/scripts/validate_digest.py" --date "$DATE" )
[[ -n "$RUN_DIR" ]] && gate+=(--run-dir "$RUN_DIR")
((HISTORICAL)) && gate+=(--historical-replay)
"${gate[@]}"

AIGREGATOR_STRICT_URLS=1 "$PYTHON" "$REPO/scripts/build.py"
"${gate[@]}" --docs "$REPO/docs"
"$PYTHON" "$REPO/scripts/verify_seo.py"

if ((DRY_RUN)); then
  echo "dry run passed; no Git writes, indexing pings, or remote state changes"
  exit 0
fi

# Pagefind is best effort but pinned to the reviewed release. It must run only
# after all publication gates have accepted the generated content.
if command -v npx >/dev/null 2>&1; then
  npx --yes pagefind@1.5.2 --site docs --output-subdir _pagefind 2>&1 | tail -5 || echo "pagefind: skipped (failed)"
fi

git add -- "digests/$DATE.md" docs
if git diff --cached --quiet; then
  echo "no new publication changes; retrying push and verification"
else
  git -c user.name="brianbaldock" -c user.email="brian@aigregator.local" commit -m "Hermes: daily digest ${DATE}"
fi
GIT_SSH_COMMAND="ssh -i ${HOME}/.ssh/ai_daily_digest_deploy -o IdentitiesOnly=yes" git push origin main
"$PYTHON" "$REPO/scripts/verify_publication.py" --date "$DATE" --docs "$REPO/docs"
"$PYTHON" "$REPO/tools/indexnow_ping.py" || echo "indexnow: skipped (failed)"
echo "published ${DATE}"
