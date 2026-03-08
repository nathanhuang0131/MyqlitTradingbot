name: optimize
description: Refactor for clarity and performance after everything is green.
steps:
  - Identify hot paths or duplication (profiling optional).
  - Refactor with no behavior change.
  - Keep diffs small; ensure tests still pass.
