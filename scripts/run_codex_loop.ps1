param(
  [string]$PromptFile = "docs/CODEX_ONE_SHOT_PROMPT.md",
  [int]$MaxRounds = 5
)

$codex = Get-Command codex -ErrorAction SilentlyContinue
if (-not $codex) {
  Write-Error "codex CLI not found in PATH"
  exit 1
}

for ($round = 1; $round -le $MaxRounds; $round++) {
  Write-Host "=== Codex round $round / $MaxRounds ==="
  Get-Content $PromptFile | codex

  $env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = "1"
  pytest -q
  if ($LASTEXITCODE -ne 0) { continue }

  python scripts/goalcheck.py
  if ($LASTEXITCODE -eq 0) {
    Write-Host "All gates green. Stopping loop."
    exit 0
  }
}

Write-Error "Loop ended without all gates green. Review the latest Codex output and rerun."
exit 1
