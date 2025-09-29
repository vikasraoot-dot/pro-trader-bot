import pandas as pd, numpy as np

def ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()

def rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    up = (delta.where(delta > 0, 0)).rolling(length).mean()
    down = (-delta.where(delta < 0, 0)).rolling(length).mean()
    rs = up / (down.replace(0, np.nan))
    out = 100 - (100 / (1 + rs))
    return out.fillna(0)

def true_range(df: pd.DataFrame) -> pd.Series:
    prev_close = df["close"].shift(1)
    tr = pd.concat([df["high"]-df["low"], (df["high"]-prev_close).abs(), (df["low"]-prev_close).abs()], axis=1).max(axis=1)
    return tr

def atr(df: pd.DataFrame, length: int = 14) -> pd.Series:
    return true_range(df).rolling(length).mean()

def adx(df: pd.DataFrame, length: int = 14):
    # Simple ADX approximation for brevity
    up_move = df["high"].diff()
    down_move = -df["low"].diff()
    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)
    tr = true_range(df)
    atr_n = tr.rolling(length).mean()
    plus_di = 100 * pd.Series(plus_dm, index=df.index).rolling(length).sum() / atr_n
    minus_di = 100 * pd.Series(minus_dm, index=df.index).rolling(length).sum() / atr_n
    dx = ( (plus_di - minus_di).abs() / (plus_di + minus_di).replace(0,np.nan) ) * 100
    adx_val = dx.rolling(length).mean()
    return adx_val.fillna(0), plus_di.fillna(0), minus_di.fillna(0)

def ema_slope_bps(series: pd.Series, bars: int = 3) -> pd.Series:
    # slope as (ema_t - ema_t-bars)/ema_t * 10,000
    return (series - series.shift(bars)) / series * 10000.0

