from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qlib_tradingbot.Diagnostics.broker import format_broker_diagnostic


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose broker/client bootstrap wiring")
    parser.add_argument("--live", action="store_true", help="Use live mode in client build check")
    parser.add_argument("--no-build", action="store_true", help="Skip client build attempt")
    args = parser.parse_args()
    print(format_broker_diagnostic(paper=not args.live, try_build=not args.no_build))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
