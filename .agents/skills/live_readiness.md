name: live_readiness
description: Harden paper/live transitions and verify explicit live safety checks.
steps:
  - Keep paper mode as default and require explicit live opt-in.
  - Validate broker credentials and API client diagnostics before live submit.
  - Require guardrails and traceability to pass for non-dry-run execution.
  - Emit clear, actionable operator diagnostics for failed readiness checks.
  - Add tests for live-path gating without network dependencies.

