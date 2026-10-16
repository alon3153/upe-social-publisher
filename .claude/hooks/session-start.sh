#!/bin/bash
# SessionStart hook: install Python deps so tests run in Claude Code on the web.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"

python3 -m pip install --quiet --disable-pip-version-check \
  -r requirements.txt -r requirements-dev.txt

