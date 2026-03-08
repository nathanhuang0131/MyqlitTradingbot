name: goal_loop
description: Iterate until success_criteria.md is met (tests + goalcheck green).
steps:
  - Read success_criteria.md and summarize what "done" means.
  - Run repo_triage skill.
  - Create a plan with <= 5 steps, each step must be verifiable.
  - Implement step 1 only.
  - Run: python scripts/goalcheck.py
  - If fail:
      - Run debug_loop skill
      - Re-run: python scripts/goalcheck.py
  - Repeat until goalcheck passes and criteria satisfied.
  - Final: write a short user-facing summary of what changed + how to run.