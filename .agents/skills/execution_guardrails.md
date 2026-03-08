name: execution_guardrails
description: Block non-dry-run orders unless broker, risk, session, and trace gates are healthy.
steps:
  - Evaluate broker config/client health/session/window/loss/exposure/duplicate checks.
  - Require decision and position trace writes before submit path.
  - Return structured block reasons and surface them in logs/UI.
  - Keep dry-run paths deterministic and offline-safe.
  - Add regression tests for blocked execution conditions.

