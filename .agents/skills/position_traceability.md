name: position_traceability
description: Ensure every open position has full thesis, model, decision, and health trace.
steps:
  - Define journal schema and persistence functions.
  - Record entry metadata at order decision/submit time.
  - Recompute position health and drift on each run.
  - Flag stale/unreviewed/contradictory positions with actionable status.
  - Write deterministic tests for persistence and health transitions.

