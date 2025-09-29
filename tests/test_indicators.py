import pandas as pd
from src.indicators import ema, rsi, adx, atr

def _dummy():
    idx = pd.date_range("2024-01-01", periods=200, freq="15min")
    price = pd.Series(range(1,201), index=idx, dtype=float)
    df = pd.DataFrame({
        "open": price, "high": price*1.01, "low": price*0.99, "close": price, "volume": 1_000_000
    })
    return df

def test_ema_monotonic():
    df = _dummy()
    e9 = ema(df["close"], 9)
    e21 = ema(df["close"], 21)
    assert (e9 >= e21).sum() > 0  # some crosses expected

def test_rsi_bounds():
    df = _dummy()
    r = rsi(df["close"], 14)
    assert (r >= 0).all() and (r <= 100).all()

def test_adx_nonnegative():
    df = _dummy()
    a, pdi, mdi = adx(df, 14)
    assert (a >= 0).all()
    assert (pdi >= 0).all() and (mdi >= 0).all()

def test_atr_positive():
    df = _dummy()
    a = atr(df, 14)
    assert (a >= 0).all()

