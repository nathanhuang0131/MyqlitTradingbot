name: write_tests
description: Add tests to lock in behavior and prevent regression.
steps:
  - For each bug/feature, add at least 1 test that would fail before the fix.
  - Prefer unit tests over integration unless necessary.
  - Keep tests deterministic (no network, no real API calls).