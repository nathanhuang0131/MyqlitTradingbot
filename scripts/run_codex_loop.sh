#!/usr/bin/env bash
set -euo pipefail

PROMPT_FILE="${1:-docs/CODEX_ONE_SHOT_PROMPT.md}"
MAX_ROUNDS="${MAX_ROUNDS:-5}"

if ! command -v codex >/dev/null 2>&1; then
  echo "codex CLI not found in PATH"
  exit 1
fi

round=1
while [ "$round" -le "$MAX_ROUNDS" ]; do
  echo "=== Codex round $round / $MAX_ROUNDS ==="
  codex < "$PROMPT_FILE"

  if PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q && python scripts/goalcheck.py; then
    echo "All gates green. Stopping loop."
    exit 0
  fi

  round=$((round + 1))
done

echo "Loop ended without all gates green. Review the latest Codex output and rerun."
exit 1
