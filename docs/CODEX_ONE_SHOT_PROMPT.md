# Codex one-shot prompt

Paste the following into Codex CLI from the repository root.

```md
You are working inside the QlibTradingbot repository.

Mission:
Make this repo the closest possible to a world-class **paper-trading-first, qlib-first, LLM-assisted, fully traceable tradingbot**.

Current constraints:
- No database: use CSV / JSONL / local files as the system of record.
- No live LLM API yet: preserve and improve the manual LLM workflow where the repo generates an upload pack, the user sends it to an external LLM, and the returned structured feedback is imported back into the repo.
- Do not remove paper/live safeguards.

Use and obey:
- `AGENTS.md`
- `success_criteria.md`
- `codex-agent/AGENTS.md`
- `codex-agent/success_criteria.md`
- `.agents/skills/*`
- `codex-agent/skills/*`

Execution rules:
1. Start with repo triage.
2. Identify the highest-value safe gap between current repo state and the success criteria.
3. Implement in small increments.
4. After each increment run:
   - `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q`
   - `python scripts/goalcheck.py`
5. Repair failures immediately.
6. Continue until all gates are green.
7. Update README / docs / changelog for any operator-visible behavior.
8. Do not stop early just because the repo already mostly works.

Priority improvements:
- strengthen qlib-first strategy ranking and model traceability
- strengthen decision fusion between qlib, manual LLM feedback, and risk state
- strengthen execution guardrails and decision logging
- improve position journal and position health review logic
- improve dashboards and operator experience using cached CSVs only
- improve manual LLM package generation and feedback import ergonomics
- remove stale code and wiring inconsistencies only when tests remain green

Expected deliverables:
- code changes
- tests added/updated
- docs updated
- concise summary of what changed
- concise summary of what still limits the repo from being truly world class

Do not declare done unless all gates are green.
```
