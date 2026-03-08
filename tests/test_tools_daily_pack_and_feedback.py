from __future__ import annotations

from pathlib import Path

import pandas as pd

from qlib_tradingbot.Tools.daily_llm_pack import generate_daily_llm_pack
from qlib_tradingbot.Tools.ingest_llm_feedback import ingest_feedback_csv
from qlib_tradingbot.Tools.perf_report import write_performance_reports


def test_daily_pack_and_feedback_ingest(tmp_path: Path) -> None:
    out_root = tmp_path / "llm_daily_pack"
    out_dir = generate_daily_llm_pack(out_root=out_root, strategy_type="short-term", dry_run=True)
    assert out_dir.is_dir()

    summary = out_dir / "summary.md"
    template = out_dir / "feedback_template.csv"
    assert summary.is_file()
    assert template.is_file()
    assert list(out_dir.glob("llm_upload_*.csv"))
    assert list(out_dir.glob("llm_prompt_*.txt"))

    df = pd.read_csv(template)
    assert "symbol" in df.columns

    # Fill first symbol
    if len(df) > 0:
        assert str(df.loc[0, "bias"]) == "Neutral"
        assert int(df.loc[0, "prob"]) == 50
        assert str(df.loc[0, "action"]) == "Hold"
        df.loc[0, "bias"] = "Bullish"
        df.loc[0, "prob"] = 70
        df.loc[0, "action"] = "Hold"
    filled = out_dir / "filled.csv"
    df.to_csv(filled, index=False)

    latest_txt, state_json = ingest_feedback_csv(input_csv=filled, out_dir=tmp_path / "llm_feedback")
    assert latest_txt.is_file()
    assert state_json.is_file()


def test_perf_report_writes_csvs(tmp_path: Path) -> None:
    data_dir = tmp_path / "Data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # create a minimal trades_ledger.csv schema
    ledger = data_dir / "trades_ledger.csv"
    pd.DataFrame(
        [
            {
                "timestamp": "2026-01-01T00:00:00Z",
                "strategy": "test",
                "symbol": "AAPL",
                "side": "BUY",
                "qty": 1,
                "fill_price": 100,
                "order_id": "1",
                "event": "CLOSE",
                "realized_pnl": 1.0,
                "fees": 0.0,
                "tags": "",
            }
        ]
    ).to_csv(ledger, index=False)

    pnl, win = write_performance_reports(data_dir=data_dir, out_dir=tmp_path / "performance")
    assert pnl.is_file()
    assert win.is_file()


def test_daily_pack_summary_fallback_without_tabulate(monkeypatch, tmp_path: Path) -> None:
    def _raise_import_error(_self, *args, **kwargs):
        raise ImportError("tabulate missing")

    monkeypatch.setattr(pd.DataFrame, "to_markdown", _raise_import_error)

    out_dir = generate_daily_llm_pack(out_root=tmp_path / "llm_daily_pack", strategy_type="short-term", dry_run=True)
    summary = (out_dir / "summary.md").read_text(encoding="utf-8")
    assert "| symbol |" in summary
