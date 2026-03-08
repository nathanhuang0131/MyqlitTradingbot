from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
MARKET_DIR = ROOT / "Data" / "market"
FIX_DIR = ROOT / "Data" / "fixtures"


def ingest() -> tuple[Path, Path]:
    MARKET_DIR.mkdir(parents=True, exist_ok=True)
    FIX_DIR.mkdir(parents=True, exist_ok=True)

    flow_path = MARKET_DIR / "fund_flows_proxy.csv"
    pos_path = MARKET_DIR / "positioning_proxy.csv"

    if not flow_path.exists():
        pd.DataFrame(
            [
                {"date": "2026-03-01", "proxy": "ETF Flow", "asset": "US Equities", "flow_usd_m": 1250},
                {"date": "2026-03-01", "proxy": "ETF Flow", "asset": "Treasuries", "flow_usd_m": 340},
            ]
        ).to_csv(flow_path, index=False)

    if not pos_path.exists():
        pd.DataFrame(
            [
                {"date": "2026-03-01", "proxy": "CFTC", "segment": "Asset Managers", "net_position": 0.62},
                {"date": "2026-03-01", "proxy": "CFTC", "segment": "Leveraged Funds", "net_position": -0.15},
            ]
        ).to_csv(pos_path, index=False)

    return flow_path, pos_path


if __name__ == "__main__":
    f, p = ingest()
    print(f"[fund_flows] wrote: {f}")
    print(f"[fund_flows] wrote: {p}")
