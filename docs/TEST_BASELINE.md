# Test Baseline

## Repository Baseline
- Date: 2026-03-02
- Scope: `tests/` only (to avoid unrelated sibling folders in `Documents`)

## Commands
- `pytest tests -q`

## Result
- Status: PASS
- Summary: `17 passed, 1 skipped, 1 warning`
- Warning: `websockets.legacy` deprecation warning from site-packages

## Notes
- Running plain `pytest -q` from `Documents` collects unrelated projects and fails.
- Project baseline test command should remain scoped to this repo's tests directory.
