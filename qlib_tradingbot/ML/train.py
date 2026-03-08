from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from qlib_tradingbot.core.features_intraday import FEATURE_COLUMNS


def train_intraday_stub(data_dir: Path) -> Path:
    model_dir = data_dir / "model_registry" / "model_cards"
    model_dir.mkdir(parents=True, exist_ok=True)
    card = {
        "model_id": "intraday_3alpha_stub_v1",
        "strategy_id": "intraday_3alpha",
        "trained_at": datetime.now(timezone.utc).isoformat(),
        "feature_columns": FEATURE_COLUMNS,
        "label": "label_fwd_ret_6",
        "backend": "stub",
        "status": "candidate",
    }
    out = model_dir / "intraday_3alpha_stub_v1.json"
    out.write_text(json.dumps(card, indent=2), encoding="utf-8")
    reg = data_dir / "model_registry" / "registry.json"
    if not reg.exists():
        reg.write_text(json.dumps({"production_model": None, "models": []}, indent=2), encoding="utf-8")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Train models for QlibTradingBot")
    ap.add_argument("--strategy", default="intraday_3alpha", help="Strategy id")
    ap.add_argument("--data-dir", default="Data", help="Data root")
    args = ap.parse_args()

    strategy = str(args.strategy).strip().lower()
    data_dir = Path(args.data_dir)
    if strategy == "intraday_3alpha":
        out = train_intraday_stub(data_dir)
        print(f"[train] wrote model card: {out}")
        return 0

    print(f"[train] no-op for strategy={strategy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
