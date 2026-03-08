name: test
description: Run the test and goal gates.
steps:
  - Run: `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest -q` (fallback to `pytest -q` if needed).
  - Run: `python scripts/goalcheck.py`
  - If failures occur, capture logs and summarize root cause.
