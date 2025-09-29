import pandas as pd
from src.risk import position_size
from src.config import load_config

def _dummy_df():
    idx = pd.date_range("2024-01-01", periods=100, freq="15min")
    close = pd.Series(100.0, index=idx)
    df = pd.DataFrame({"open":close, "high":close*1.001, "low":close*0.999, "close":close, "volume":1_000_000})
    return df

def test_size_positive_qty():
    cfg = load_config("config.yaml")
    df = _dummy_df()
    plan = position_size(cfg, df, price=100.0, equity=100_000.0)
    assert plan.qty >= 1
    assert plan.stop_price < 100.0
    assert plan.take_profit > 100.0

