import pandas as pd
import numpy as np

from qlib_tradingbot.Qlib.dataset import _compute_features


def make_bars():
    # 2 symbols, 50 bars each
    rows=[]
    base=pd.Timestamp("2026-02-24 14:30:00", tz="UTC")
    for sym in ["AAPL","MSFT"]:
        px=100.0 if sym=="AAPL" else 200.0
        for i in range(60):
            ts=base+pd.Timedelta(minutes=5*i)
            close=px*(1+0.0005*np.sin(i/5))
            rows.append({"symbol":sym,"datetime":ts,"open":close*0.999,"high":close*1.001,"low":close*0.998,"close":close,"volume":1000+i})
    return pd.DataFrame(rows)

def test_compute_features_shape():
    bars=make_bars()
    feat, features=_compute_features(bars)
    assert "LABEL0" in feat.columns
    for c in features:
        assert c in feat.columns
    # multi-index
    assert isinstance(feat.index, pd.MultiIndex)
    assert feat.index.nlevels==2
