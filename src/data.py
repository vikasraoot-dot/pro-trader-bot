import pandas as pd, numpy as np, yfinance as yf
from typing import Tuple, Dict, List
from .config import Config

def download_ohlc(symbol: str, start: str, end: str, interval: str) -> pd.DataFrame:
    df = yf.download(symbol, start=start, end=end, interval=interval, auto_adjust=False, progress=False)
    df = df.rename(columns=str.lower)
    if "adj close" in df.columns:
        df = df.drop(columns=["adj close"])
    df = df.dropna()
    return df

def rolling_dollar_vol(df: pd.DataFrame, win: int = 20) -> pd.Series:
    return (df["close"] * df.get("volume", 0)).rolling(win).mean()

def illiquidity_pass(df: pd.DataFrame, min_price: float, min_dollar_vol: float) -> bool:
    try:
        last = df.iloc[-1]
        if float(last["close"]) < min_price: return False
        if rolling_dollar_vol(df).iloc[-1] < min_dollar_vol: return False
    except Exception:
        return False
    return True

