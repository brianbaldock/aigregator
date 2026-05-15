#!/usr/bin/env bash
# Local preview: build site + pagefind index, serve on localhost:8765.
# No git, no push. Iterate freely, then run scripts/publish.sh when happy.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${PORT:-8765}"
BIND="${BIND:-127.0.0.1}"

cd "$REPO"

echo "==> building site"
"${REPO}/.venv/bin/python" scripts/build.py

if command -v npx >/dev/null 2>&1; then
  echo "==> indexing with pagefind"
  npx --yes pagefind --site docs --output-subdir _pagefind 2>&1 | tail -3 || echo "pagefind: skipped"
fi

echo ""
echo "==> serving docs/ on http://${BIND}:${PORT}"
echo "    LAN access: http://$(hostname -I 2>/dev/null | awk '{print $1}'):${PORT}"
echo "    ctrl+c to stop. re-run after edits to rebuild."
echo ""
cd docs
exec python3 -m http.server "$PORT" --bind "$BIND"
