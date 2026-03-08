name: debug
description: Debug failing tests/goalcheck without guessing.
steps:
  - Reproduce the failure locally (same command).
  - Add targeted logs/instrumentation if needed.
  - Fix root cause; do not delete failing tests.
  - Add regression test if bug fix.
