from pathlib import Path

from qlib_tradingbot.core.models import Signal
from qlib_tradingbot.Execution.engine import execute_signals
import qlib_tradingbot.Execution.orders as orders

class Pos:
    def __init__(self, symbol, qty):
        self.symbol=symbol
        self.qty=str(qty)

class FakeTradeClient:
    def get_all_positions(self):
        return [Pos("MSFT", 1)]
    def get_position(self, symbol):
        if symbol.upper()=="MSFT":
            return Pos("MSFT", 1)
        raise Exception("no position")
    def submit_order(self, order_req):
        return {"id":"TEST123"}

def test_execute_signals_dry_run():
    tc=FakeTradeClient()
    sigs=[
        Signal(symbol="AAPL", side="BUY", strategy_id="S", strategy_version="1", timeframe="5Min", price_basis=100.0),
        Signal(symbol="MSFT", side="SELL", strategy_id="S", strategy_version="1", timeframe="5Min", price_basis=200.0),
    ]
    res=execute_signals(tc, sigs)
    assert len(res)==2
    assert res[0].symbol=="AAPL"
    assert res[1].symbol=="MSFT"


def test_execute_signals_dry_run_no_alpaca_and_records_orders(monkeypatch, tmp_path: Path):
    tc = FakeTradeClient()
    sigs = [
        Signal(symbol="AAPL", side="BUY", strategy_id="S", strategy_version="1", timeframe="5Min", price_basis=100.0),
        Signal(symbol="MSFT", side="SELL", strategy_id="S", strategy_version="1", timeframe="5Min", price_basis=200.0),
    ]

    def _fail_import():
        raise AssertionError("alpaca import must not happen in dry_run execution")

    monkeypatch.setattr(orders, "_import_alpaca", _fail_import, raising=False)

    res = execute_signals(tc, sigs, dry_run=True, dry_run_output_dir=tmp_path)

    assert len(res) == 2
    assert all(r.ok for r in res)
    assert all(r.submitted is False for r in res)
    assert (tmp_path / "mock_orders.csv").is_file()
    assert (tmp_path / "mock_orders.jsonl").is_file()
