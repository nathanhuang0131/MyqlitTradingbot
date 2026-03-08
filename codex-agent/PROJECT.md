# QlibTradingbot — Codex Agent Project (v2)

## Mission
Iterate the repository until:
1) `pytest -q` passes
2) `python scripts/goalcheck.py` passes
3) `success_criteria.md` is satisfied

## Repo entrypoints
- Console UI: `python main.py --ui`
- Non-UI run: `python main.py`
- Goal check: `python scripts/goalcheck.py`

## Key folders
- `qlib_tradingbot/` — main package
- `qlib_tradingbot/Strategies/` — long/short term + intraday strategies
- `qlib_tradingbot/Execution/` — risk + order placement + life-cycle
- `qlib_tradingbot/LLM/` — post-market package + feedback gating
- `qlib_tradingbot/Reporting/` — CSV logging + PnL/win-rate utilities
- `Data/` — output artifacts (CSV, prompts, feedback)

## Guardrails
- Paper trading is the default. Live trading must be explicitly enabled with a flag.
- No network calls in unit tests; all tests must be deterministic and offline.

## Agent loop
Use the `goal_loop` skill (in `.agents/skills/goal_loop.md`) to iterate until green.
