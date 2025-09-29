import pandas as pd
from .indicators import ema, adx, atr

def compute_htf_regime(htf: pd.DataFrame, adx_min: float, chop_max: float):
    ema50 = ema(htf["close"], 50)
    ema200 = ema(htf["close"], 200)
    adx_val, _, _ = adx(htf, 14)
    trend = (ema50 > ema200) & (adx_val >= adx_min)
    chop = (adx_val <= chop_max)
    return trend.fillna(False), chop.fillna(False)

def high_volatility_flag(df30m: pd.DataFrame, mult: float = 2.0) -> bool:
    # ATR% 30m against 60d median (very rough proxy)
    a = atr(df30m, 14)
    atr_pct = (a / df30m["close"]) * 100
    med = atr_pct.rolling(60*13//14).median()  # ~60 trading days on 30m bars rough
    flag = (atr_pct.iloc[-1] > mult * (med.iloc[-1] if not pd.isna(med.iloc[-1]) else atr_pct.iloc[-1]))
    return bool(flag)

