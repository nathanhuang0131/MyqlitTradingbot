# Success Criteria — QlibTradingbot v3 goal loop

## 1. Engineering gates
- [ ] `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` passes
- [ ] `python scripts/goalcheck.py` passes

## 2. Codex autonomy assets exist and are useful
- [ ] Root `AGENTS.md` exists and clearly instructs an iterate-until-green loop
- [ ] Root `success_criteria.md` matches the current repo mission
- [ ] `codex-agent/AGENTS.md` exists and mirrors the operating model
- [ ] `codex-agent/success_criteria.md` exists and is actionable
- [ ] `.agents/skills/` contains the world-class tradingbot support skills used by the repo
- [ ] `docs/CODEX_ONE_SHOT_PROMPT.md` exists
- [ ] `scripts/run_codex_loop.ps1` exists
- [ ] `scripts/run_codex_loop.sh` exists

## 3. Qlib-first trading core
- [ ] `qlib_tradingbot/core/qlib_signal_engine.py` exists and imports
- [ ] At least the major strategy paths route primary ranking through qlib outputs or a qlib-first abstraction
- [ ] Signal outputs are normalized enough for downstream decision fusion and dashboards

## 4. Safe execution
- [ ] Broker bootstrap supports `.env` loading from repo root
- [ ] Both Alpaca key naming schemes are supported
- [ ] Broker diagnostics are available via script
- [ ] Submit paths are protected by guardrails
- [ ] Dry-run remains default-safe

## 5. Manual LLM workflow is first-class
- [ ] A daily/offline LLM package generator exists
- [ ] It writes upload CSV, prompt, summary, and feedback template
- [ ] Feedback CSV ingest writes latest text + bias state JSON
- [ ] Strategy execution can read the resulting LLM bias state
- [ ] This workflow is documented in README or docs

## 6. Position traceability
- [ ] Decision trace output exists
- [ ] Position journal output exists
- [ ] Position health output exists
- [ ] Position review status is visible in dashboards or CSV outputs

## 7. Dashboards
- [ ] Dashboard entrypoint exists
- [ ] Account, Market, Fund Flows, and Position Trace pages exist
- [ ] Pages are cached-data-first and degrade gracefully when files are missing
- [ ] Pages are import-safe for tests

## 8. Test quality
- [ ] Unit tests run offline
- [ ] Decision fusion tests exist
- [ ] Execution guardrail tests exist
- [ ] LLM package and feedback ingest tests exist
- [ ] Position traceability tests exist

## 9. Operator usability
- [ ] README explains broker setup, diagnostics, run flow, dashboard, and manual LLM loop
- [ ] There is at least one one-shot Codex prompt file for autonomous iteration
- [ ] There is at least one loop script for repeated Codex execution
