from __future__ import annotations

import warnings

# Reduce noisy third-party warnings during monitoring
try:
    from pandas.errors import SettingWithCopyWarning
    warnings.filterwarnings("ignore", category=SettingWithCopyWarning)
except Exception:
    pass

import json
import time
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import pandas as pd

from qlib_tradingbot.Brokers.alpaca_clients import build_clients
from qlib_tradingbot.Execution.engine import execute_signals
from qlib_tradingbot.Strategies.scalp_pipeline_qlib import (
    PipelineConfig,
    Stage2Config,
    Stage3Config,
    run_3stage_qlib_scalp_pipeline,
    stage3_qlib_score,
)
from qlib_tradingbot.Strategies.scalping_qlib import signals_from_predictions
from qlib_tradingbot.Strategies.hybrid_bias_trigger import signals_from_bias_and_1m_trigger
from qlib_tradingbot.Data.batch_bars import fetch_1m_bars_batch
from qlib_tradingbot.Data.logs import write_csv_atomic
from qlib_tradingbot.config import (
    PAPER,
    MAX_DOLLARS_PER_TRADE,
    DRY_RUN,
)


def _load_universe(path: Path) -> List[str]:
    if not path.exists():
        raise FileNotFoundError(f"Universe file not found: {path}")
    df = pd.read_csv(path)
    col = "Symbol" if "Symbol" in df.columns else ("symbol" if "symbol" in df.columns else df.columns[0])
    return [str(x).strip().upper() for x in df[col].dropna().tolist() if str(x).strip()]


def _prompt_float(label: str, default: float) -> float:
    s = input(f"{label} [{default}]: ").strip()
    return float(s) if s else float(default)


def _prompt_int(label: str, default: int) -> int:
    s = input(f"{label} [{default}]: ").strip()
    return int(s) if s else int(default)


def run_once_interactive() -> None:
    print("\n=== QLIB TradingBot v2 (3-stage DT-2 scalping, paper) ===\n")
    print(f"Paper: {PAPER} | DRY_RUN: {DRY_RUN}\n")

    # Build clients
    data_client, trade_client = build_clients(paper=PAPER)

    # Pipeline params (user-tunable)
    print("Stage 2 prescreen parameters (daily bars):")
    s2 = Stage2Config(
        min_price=_prompt_float("  Min price", Stage2Config().min_price),
        min_avg_volume_20d=_prompt_float("  Min 20D avg volume", Stage2Config().min_avg_volume_20d),
        min_atr_pct_14d=_prompt_float("  Min ATR% (14D)", Stage2Config().min_atr_pct_14d),
        max_spread_proxy_20d=_prompt_float("  Max spread proxy (20D)", Stage2Config().max_spread_proxy_20d),
        keep_top_n=_prompt_int("  Keep top N after prescreen", Stage2Config().keep_top_n),
    )

    print("\nStage 3 Qlib scoring parameters (5-minute bars):")
    s3 = Stage3Config(
        top_n_signals=_prompt_int("  Top N signals", Stage3Config().top_n_signals),
        allow_shorts=(input("  Allow shorts? (y/N): ").strip().lower() == "y"),
        monitor_top_n_by_pred=_prompt_int("  Monitor top N by prediction if none pass thresholds", Stage3Config().monitor_top_n_by_pred),
        min_stage3_symbols=_prompt_int("  Minimum symbols for Stage 3 training/monitoring", Stage3Config().min_stage3_symbols),
    )

    lookback_daily = _prompt_int("\nDaily lookback days (for Stage 2)", PipelineConfig().lookback_days_daily)
    lookback_5m = _prompt_int("5m lookback days (for Stage 3)", PipelineConfig().lookback_days_5m)

    cfg = PipelineConfig(stage2=s2, stage3=s3, lookback_days_daily=lookback_daily, lookback_days_5m=lookback_5m)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    corr_id = f"qlibv2-{run_id}"

    print("\nRunning Stage 1→2→3 pipeline (Stage 1 discovers from Alpaca active assets)...")
    debug = run_3stage_qlib_scalp_pipeline(
        data_client=data_client,
        trade_client=trade_client,
        run_id=run_id,
        correlation_id=corr_id,
        cfg=cfg,
    )

    print("\n--- Pipeline summary ---")
    print(json.dumps(debug, indent=2))

    trade_universe_path = Path("Data/universe_trade_today.csv")
    if not trade_universe_path.exists():
        print("No trade universe produced. Check Stage 2 filters or Alpaca data access.")
        return

    trade_universe = _load_universe(trade_universe_path)
    print(f"\nTrade universe ready: {len(trade_universe)} symbols (Data/universe_trade_today.csv)")

    start_monitor = (input("\nStart monitoring loop now? (y/N): ").strip().lower() == "y")
    if not start_monitor:
        print("\nDone. You can run the monitor loop later using Data/universe_trade_today.csv.")
        return

    interval_min = _prompt_int("Monitor interval minutes", 5)
    hours = _prompt_int("Run monitoring for how many hours", 6)
    use_hybrid = (input("Use HYBRID mode (5m ML bias + 1m trigger)? (y/N): ").strip().lower() == "y")

    print("\nMonitoring loop started. (Press Ctrl+C to stop)")
    end_ts = time.time() + (hours * 3600)

    while time.time() < end_ts:
        loop_ts = datetime.now(timezone.utc).isoformat()
        print(f"\n[{loop_ts}] Scoring {len(trade_universe)} symbols...")

        preds, bars_df = stage3_qlib_score(
            data_client,
            symbols=trade_universe,
            batch_cfg=cfg.batch,
            lookback_days_5m=int(cfg.lookback_days_5m),
            cfg=cfg.stage3,
        )

        # price basis from latest close in bars
        latest_close = (
            bars_df.sort_values(["symbol", "datetime"])
                .groupby("symbol")["close"]
                .last()
                .to_dict()
        ) if bars_df is not None and not bars_df.empty else {}

        if use_hybrid:
            # Fetch 1-minute bars only for the current universe (cached)
            bars_1m_map = fetch_1m_bars_batch(
                data_client,
                symbols=trade_universe,
                lookback_days=2,
                cfg=cfg.batch,
            )
            selection = signals_from_bias_and_1m_trigger(
                preds,
                bars_1m_map,
                top_n=int(cfg.stage3.top_n_signals),
                allow_shorts=bool(cfg.stage3.allow_shorts),
                price_basis_by_symbol=latest_close,
            )
        else:
            selection = signals_from_predictions(
                preds,
                top_n=int(cfg.stage3.top_n_signals),
                allow_shorts=bool(cfg.stage3.allow_shorts),
                price_basis_by_symbol=latest_close,
            )

        # Persist snapshots
        write_csv_atomic("Data/qlib_preds_monitor_latest.csv", preds.reset_index().rename(columns={0: "pred"}) if preds is not None and len(preds) else pd.DataFrame())
        write_csv_atomic("Data/trade_signals_monitor_latest.csv", selection.snapshot if selection.snapshot is not None else pd.DataFrame())

        if selection.snapshot is None or selection.snapshot.empty:
            print("No signals hit thresholds this interval.")
        else:
            print(selection.snapshot.head(30).to_string(index=False))

            if DRY_RUN:
                print("DRY_RUN=1 -> no orders submitted.")
            else:
                do_trade = (input("Submit these orders to Alpaca now? (y/N): ").strip().lower() == "y")
                if do_trade:
                    results = execute_signals(trade_client, selection.signals)
                    print("--- Execution results ---")
                    for r in results:
                        print(asdict(r))

        # sleep until next interval
        sleep_s = max(5, int(interval_min * 60))
        for _ in range(sleep_s // 5):
            time.sleep(5)
            if time.time() >= end_ts:
                break

    print("\nMonitoring loop finished.")
