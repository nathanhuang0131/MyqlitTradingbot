name: debug_loop
description: Fix failing tests/builds in a tight loop.
steps:
  - Read the failing output carefully.
  - Identify root cause (not symptom).
  - Make minimal code change.
  - Add/adjust test if needed.
  - Re-run the failing test(s) first, then full suite.