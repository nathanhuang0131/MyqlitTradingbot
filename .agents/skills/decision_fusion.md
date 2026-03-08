name: decision_fusion
description: Fuse qlib rank/confidence with governed LLM bias and risk state into a deterministic final action.
steps:
  - Build typed decision input/output models.
  - Implement deterministic policy rules (buy/sell/reduce/hold/block) with explicit reasons.
  - Include conflict handling (qlib bullish + llm bearish, etc.) and guardrail-aware blocking.
  - Persist fusion records to decision trace logs.
  - Add deterministic unit tests for rule outcomes.

