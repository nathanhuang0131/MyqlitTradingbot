from __future__ import annotations

import argparse
import csv
import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from qlib_tradingbot.Brokers.alpaca_gateway import get_market_clock
from qlib_tradingbot.Strategies.base import StrategyContext
from qlib_tradingbot.Strategies.registry import default_registry
from qlib_tradingbot.Execution.strategy_runner import StrategyRunner
from qlib_tradingbot.Tools.perf_report import write_performance_reports
from qlib_tradingbot.Utils.timezone_utils import in_ny_trading_window


def _build_clients(paper: bool, dry_run: bool):
    if dry_run:
        return None, None
    try:
        from qlib_tradingbot.Brokers.alpaca_clients import build_clients

        return build_clients(paper=paper)
    except Exception as exc:
        from qlib_tradingbot.Brokers.alpaca_clients import diagnose_broker_setup

        diag = diagnose_broker_setup(paper=paper, try_build=False)
        msg = (
            f"Broker client initialization failed: {exc}\n"
            f"env_file={diag.get('env_file')}\n"
            f"broker_configured={diag.get('broker_configured')} "
            f"alpaca_available={diag.get('alpaca_available')} "
            f"mode={diag.get('mode')}\n"
            "Fix credentials (.env or env vars) and ensure alpaca-py is installed."
        )
        raise SystemExit(msg) from exc


def _append_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        if not exists:
            w.writeheader()
        w.writerows(rows)


def _append_trade_ledger(data_dir: Path, orders: list[object], strategy: str) -> None:
    rows = []
    now = datetime.now(timezone.utc).isoformat()
    for o in orders:
        payload = asdict(o) if hasattr(o, "__dataclass_fields__") else {}
        rows.append(
            {
                "timestamp": now,
                "strategy": strategy,
                "symbol": str(payload.get("symbol", "")),
                "side": str(payload.get("action", "")),
                "qty": 0,
                "fill_price": 0.0,
                "order_id": str(payload.get("order_id", "")),
                "event": "INTENT",
                "realized_pnl": 0.0,
                "fees": 0.0,
                "tags": "intraday_3alpha",
            }
        )
    _append_csv(data_dir / "trades_ledger.csv", rows)


def _write_intents(data_dir: Path, run_id: str, orders: list[object]) -> Path:
    rows = []
    for o in orders:
        p = asdict(o) if hasattr(o, "__dataclass_fields__") else {}
        rows.append(
            {
                "run_id": run_id,
                "symbol": str(p.get("symbol", "")),
                "action": str(p.get("action", "")),
                "submitted": bool(p.get("submitted", False)),
                "ok": bool(p.get("ok", False)),
                "error": str(p.get("error", "") or ""),
            }
        )
    out = data_dir / "intents" / "intents.csv"
    _append_csv(out, rows)
    return out


def _write_runner_log(data_dir: Path, payload: dict) -> None:
    path = data_dir / "run_log.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=True, default=str) + "\n")


def _run_once(args, data_dir: Path, data_client, trade_client) -> dict:
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    cfg = {
        "dry_run": bool(args.paper and not args.live),
        "allow_shorts": True,
        "qlib_stub_mode": True,
        "buy_threshold": float(args.buy_threshold),
        "sell_threshold": float(args.sell_threshold),
        "llm_bias_state_path": str(data_dir / "llm_feedback" / "llm_bias_state.json"),
        "universe_symbols": [s.strip().upper() for s in str(args.symbols).split(",") if s.strip()],
    }
    ctx = StrategyContext(
        run_id=run_id,
        correlation_id=f"corr-{run_id}",
        now_utc=datetime.now(timezone.utc),
        data_dir=str(data_dir),
        config=cfg,
        data_client=data_client,
        trade_client=trade_client,
    )
    strategy = default_registry().factories()[args.strategy](ctx)
    out = StrategyRunner().run_once(
        strategy,
        ctx,
        dry_run=bool(cfg["dry_run"]),
        dry_run_output_dir=data_dir / "trade_history",
        allow_shorts=True,
    )

    report = strategy.post_trade_reporting()
    intents_path = _write_intents(data_dir, run_id, out.orders)
    _append_trade_ledger(data_dir, out.orders, args.strategy)
    write_performance_reports(data_dir=data_dir, out_dir=data_dir / "performance")

    return {
        "run_id": run_id,
        "signals_rows": int(out.signals_size),
        "orders_rows": int(out.orders_size),
        "signals_path": str(report.get("signals_snapshot", data_dir / "signals" / "intraday_3alpha_signals.csv")),
        "intents_path": str(intents_path),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Autonomous CLI runner")
    ap.add_argument("--strategy", default="intraday_3alpha")
    ap.add_argument("--mode", choices=["once", "loop"], default="once")
    ap.add_argument("--rebalance-min", type=int, default=15)
    ap.add_argument("--ny-window", default="09:30-15:55")
    ap.add_argument("--symbols", default="AAPL,MSFT,SPY")
    ap.add_argument("--paper", action="store_true", default=True)
    ap.add_argument("--live", action="store_true", default=False)
    ap.add_argument("--max-iter", type=int, default=1)
    ap.add_argument("--buy-threshold", type=float, default=0.05)
    ap.add_argument("--sell-threshold", type=float, default=-0.05)
    ap.add_argument("--data-dir", default="Data")
    args = ap.parse_args()

    if args.strategy != "intraday_3alpha":
        raise SystemExit(f"unsupported strategy: {args.strategy}")

    if args.live:
        allow = {s.strip().lower() for s in str(Path(args.data_dir).joinpath("live_allowlist.txt").read_text(encoding="utf-8")).splitlines()} if Path(args.data_dir).joinpath("live_allowlist.txt").exists() else set()
        if args.strategy.lower() not in allow:
            raise SystemExit("live mode blocked: strategy not in Data/live_allowlist.txt")

    paper = bool(not args.live)
    dry_run = bool(paper)
    data_dir = Path(args.data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)
    start, end = [x.strip() for x in str(args.ny_window).split("-", 1)]

    data_client, trade_client = _build_clients(paper=paper, dry_run=dry_run)
    sleep_sec = max(5, int(args.rebalance_min) * 60)
    loops = int(args.max_iter) if args.mode == "loop" else 1

    for idx in range(loops):
        now = datetime.now(timezone.utc)
        within_window = in_ny_trading_window(now, start, end)
        market_open = True
        if trade_client is not None:
            market_open = bool(get_market_clock(trade_client).is_open)

        if not within_window or not market_open:
            payload = {
                "ts": now.isoformat(),
                "status": "market_closed",
                "strategy": args.strategy,
                "within_window": bool(within_window),
                "market_open": bool(market_open),
                "sleep_sec": sleep_sec,
            }
            _write_runner_log(data_dir, payload)
            if args.mode == "loop" and idx < loops - 1:
                time.sleep(sleep_sec)
                continue
            break

        result = _run_once(args, data_dir, data_client, trade_client)
        payload = {"ts": now.isoformat(), "status": "ok", **result}
        _write_runner_log(data_dir, payload)

        if args.mode == "loop" and idx < loops - 1:
            time.sleep(sleep_sec)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
