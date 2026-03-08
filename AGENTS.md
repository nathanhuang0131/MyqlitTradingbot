# AGENTS.md — QlibTradingbot World-Class Goal Loop

## Mission
Turn this repository into the strongest possible **paper-trading-first, qlib-first, LLM-assisted tradingbot** without introducing uncontrolled live-trading risk.

The bot should be:
- qlib-first for ranking and signal generation
- execution-safe by default
- fully testable offline
- CSV-state driven (no database required)
- traceable for every decision and open position
- ready for later LLM API integration, while supporting manual CSV-based LLM feedback today

## Completion gates
Do not declare success unless all are true:
1. `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` passes
2. `python scripts/goalcheck.py` passes
3. `success_criteria.md` is satisfied
4. README / docs are updated when behavior changes
5. Any new behavior has tests or explicit rationale for why it cannot be unit tested

## Operating loop
Repeat until green:
1. Repo triage
2. Choose the highest-value smallest safe increment
3. Implement minimally
4. Run tests + goalcheck
5. Repair failures immediately
6. Update docs/changelog if behavior changed
7. Continue until all gates are green

## Priorities
1. Safety and correctness
2. Deterministic tests
3. Traceability
4. Architecture cleanliness
5. Dashboard clarity
6. Performance optimization

## Non-negotiables
- Never remove or weaken tests just to get green
- Never bypass risk checks for live/paper submit paths
- Never make live trading the default
- Never silently swallow broker, config, or execution failures
- Never add network dependence to unit tests
- Prefer adapters, stubs, fixtures, and cached CSV inputs

## Current intended architecture
- `qlib_tradingbot/core/` — qlib-first signal and portfolio core
- `qlib_tradingbot/Decision/` — qlib + LLM + risk fusion
- `qlib_tradingbot/Execution/` — order adapters, guardrails, broker submission
- `qlib_tradingbot/Traceability/` — decision trace, position journal, health reviews
- `qlib_tradingbot/LLM/` — prompt building, offline package generation, feedback ingest/gating
- `qlib_tradingbot/dashboards/` — cached-data-first operational dashboards
- `Data/` — CSV and JSONL operational state

## Required system qualities
- qlib is the primary model/ranking engine
- LLM is a governed assist layer, not an uncontrolled autonomous trader
- every order attempt has a decision trace
- every open position has thesis, target, stop, horizon, and status
- dashboards reflect real cached state, not fake placeholder numbers
- all important workflows run without a database

## Manual LLM workflow assumption
This repo currently supports a manual LLM loop:
1. Generate package files locally
2. User uploads CSV + prompt to an external LLM manually
3. User pastes model output back into `feedback_template.csv`
4. Ingest CSV back into the bot
5. Strategy runner uses resulting bias state in governed gating

Codex should preserve and improve this workflow unless explicitly asked to replace it with a direct API integration.

## Suggested execution order for large upgrades
1. Keep tests + goalcheck green
2. Harden broker/config/bootstrap
3. Harden decision fusion + execution guardrails
4. Improve position traceability and review logic
5. Improve dashboard operations and empty states
6. Improve docs and operator workflows
7. Optimize/refactor only after correctness is stable

## Definition of “closest possible to world class” in this repo
- qlib-first signal generation is real and central
- LLM manual-feedback path is smooth and structured
- decision fusion is explicit and test-covered
- open positions are continuously reviewable via CSV + dashboard
- guardrails block unsafe submissions
- repo is easy for Codex to iterate autonomously

## Expected deliverables from Codex
- code changes
- tests added/updated
- docs updated
- concise changelog/note
- final summary of what changed, what remains, and any operator action needed
