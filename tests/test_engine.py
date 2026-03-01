from qlib_tradingbot.Core.models import Signal
from qlib_tradingbot.Execution.engine import execute_signals

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
