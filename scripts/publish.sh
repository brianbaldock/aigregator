#!/usr/bin/env bash
# AIgregator publisher: build site, commit today's digest, push to GitHub Pages.
# Called by the cron job after it writes digests/YYYY-MM-DD.md
set -euo pipefail

REPO="${HOME}/projects/AIgregator"
KEY="${HOME}/.ssh/ai_daily_digest_deploy"
DATE="${1:-$(date -u +%Y-%m-%d)}"

cd "$REPO"

# Set local git identity (so commits don't depend on global config)
git config user.name "brianbaldock"
git config user.email "brian@aigregator.local"

# Build
"${REPO}/.venv/bin/python" scripts/build.py

# Pagefind search index — best-effort, never fails the publish
if command -v npx >/dev/null 2>&1; then
  npx --yes pagefind --site docs --output-subdir _pagefind 2>&1 | tail -5 || echo "pagefind: skipped (failed)"
fi

# Commit + push if there are changes
if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git commit -m "Hermes: daily digest ${DATE}"
  GIT_SSH_COMMAND="ssh -i ${KEY} -o IdentitiesOnly=yes" git push origin main
  echo "published ${DATE}"
else
  echo "no changes to publish"
fi
