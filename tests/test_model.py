import pytest
import pandas as pd
import numpy as np

try:
    import qlib  # noqa: F401
    QLIB_OK = True
except Exception:
    QLIB_OK = False

from qlib_tradingbot.Qlib.dataset import build_qlib_dataset_from_bars
from qlib_tradingbot.Qlib.model import train_lightgbm, predict

def make_bars():
    rows=[]
    base=pd.Timestamp("2026-01-02 14:30:00", tz="UTC")
    for sym in ["AAPL","MSFT","QQQ"]:
        px=100.0+10*len(sym)
        for i in range(120):
            ts=base+pd.Timedelta(minutes=5*i)
            close=px*(1+0.0003*np.sin(i/7))+0.01*i
            rows.append({"symbol":sym,"datetime":ts,"open":close*0.999,"high":close*1.001,"low":close*0.998,"close":close,"volume":1000+i})
    return pd.DataFrame(rows)

@pytest.mark.skipif(not QLIB_OK, reason="pyqlib not installed in test environment")
def test_train_predict_smoke():
    bars=make_bars()
    bundle=build_qlib_dataset_from_bars(
        bars,
        train_start="2026-01-02",
        train_end="2026-01-03",
        valid_end="2026-01-04",
        test_end="2026-01-05",
    )
    model=train_lightgbm(bundle, params={"learning_rate":0.1,"num_leaves":15,"max_depth":4,"num_threads":1})
    preds=predict(model, bundle, segment="test")
    assert isinstance(preds, pd.Series)
    assert len(preds)>0
