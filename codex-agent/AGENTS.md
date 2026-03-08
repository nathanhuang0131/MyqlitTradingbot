# Codex Agent Instructions — QlibTradingbot v3

Use this repository as an iterate-until-green project.

## Goal
Make the bot as close as possible to a world-class qlib-first, LLM-assisted, traceable paper-trading system while keeping all engineering gates green.

## Mandatory gates
- `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
- `python scripts/goalcheck.py`
- `success_criteria.md`

## Work style
- Make small safe increments
- Run tests after each increment
- Fix failures immediately
- Prefer deterministic offline behavior
- Preserve paper-trading-first safety
- Update docs when workflows change

## Special focus areas
- qlib-first strategy ranking
- manual LLM package + feedback loop
- decision fusion
- execution guardrails
- position traceability
- dashboard operations
