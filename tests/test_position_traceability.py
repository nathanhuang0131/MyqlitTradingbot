from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from qlib_tradingbot.Decision.models import DecisionRecord
from qlib_tradingbot.Traceability.position_trace import (
    review_position_health,
    write_decision_trace,
    upsert_position_journal,
)


def test_trace_writes_and_journal_persists(tmp_path: Path):
    data_dir = tmp_path
    rec = DecisionRecord(
        ts_utc=datetime.now(timezone.utc).isoformat(),
        run_id="r1",
        correlation_id="c1",
        symbol="AAPL",
        strategy_id="scalping",
        model_id="m1",
        qlib_alpha=0.5,
        qlib_confidence=0.7,
        llm_bias="Bullish",
        llm_probability=80.0,
        final_action="buy",
        blocked=False,
        reasons=["aligned"],
    )
    write_decision_trace(data_dir, [rec])
    upsert_position_journal(
        data_dir,
        [rec],
        expected_horizon="1D",
        entry_thesis="qlib+llm aligned",
        target=110.0,
        stop=95.0,
    )

    assert (data_dir / "decision_trace.jsonl").exists()
    assert (data_dir / "position_journal.csv").exists()


def test_position_health_review_flags_stale(tmp_path: Path):
    data_dir = tmp_path
    rec = DecisionRecord(
        ts_utc="2025-01-01T00:00:00+00:00",
        run_id="old",
        correlation_id="oldc",
        symbol="TSLA",
        strategy_id="intraday_3alpha",
        model_id="m2",
        qlib_alpha=0.2,
        qlib_confidence=0.5,
        llm_bias="Neutral",
        llm_probability=55.0,
        final_action="buy",
        blocked=False,
        reasons=["entry"],
    )
    upsert_position_journal(
        data_dir,
        [rec],
        expected_horizon="1D",
        entry_thesis="test",
        target=210.0,
        stop=180.0,
    )
    health = review_position_health(data_dir, now_utc=datetime(2026, 3, 8, tzinfo=timezone.utc))
    assert not health.empty
    assert "latest_status" in health.columns
    assert set(health["latest_status"]).intersection({"watch", "risk", "invalidated"})

