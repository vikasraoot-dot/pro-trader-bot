import os
from typing import Optional
import pandas as pd
from .config import Config

# Optional yfinance fallback
try:
    import yfinance as yf  # noqa
    HAVE_YF = True
except Exception:
    HAVE_YF = False

# Alpaca Market Data
try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    HAVE_ALPACA_DATA = True
except Exception:
    HAVE_ALPACA_DATA = False


def _has_alpaca_creds() -> bool:
    return bool(os.getenv("ALPACA_KEY") and os.getenv("ALPACA_SECRET")) or bool(
        os.getenv("APCA_API_KEY_ID") and os.getenv("APCA_API_SECRET_KEY")
    )


def _alpaca_timeframe(tf_str: str):
    tf_str = tf_str.strip().lower()
    if tf_str.endswith("m"):
        n = int(tf_str[:-1])
        return TimeFrame(n, TimeFrameUnit.Minute)
    if tf_str.endswith("h"):
        n = int(tf_str[:-1])
        return TimeFrame(n, TimeFrameUnit.Hour)
    if tf_str in ("1d", "d", "day", "daily"):
        return TimeFrame.Day
    return TimeFrame(15, TimeFrameUnit.Minute)


def _download_alpaca(symbol: str, start: str, end: str, tf_str: str) -> pd.DataFrame:
    key = os.getenv("ALPACA_KEY") or os.getenv("APCA_API_KEY_ID")
    sec = os.getenv("ALPACA_SECRET") or os.getenv("APCA_API_SECRET_KEY")

    client = StockHistoricalDataClient(api_key=key, secret_key=sec)
    tf = _alpaca_timeframe(tf_str)

    req = StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=tf,
        start=pd.Timestamp(start).tz_localize("America/New_York"),
        end=pd.Timestamp(end).tz_localize("America/New_York"),
        adjustment=None,
        limit=None,
        feed="iex",  # free feed for paper
    )
    bars = client.get_stock_bars(req)
    if symbol not in bars.data:
        return pd.DataFrame()

    df = pd.DataFrame([b.__dict__ for b in bars.data[symbol]])
    # Normalize
    rename_map = {"o": "open", "h": "high", "l": "low", "c": "close", "v": "volume", "t": "timestamp"}
    for src, dst in rename_map.items():
        if src in df.columns and dst not in df.columns:
            df[dst] = df[src]

    if "timestamp" in df.columns:
        df = df.set_index(pd.to_datetime(df["timestamp"], utc=True)).tz_convert("America/New_York")
        df = df.drop(columns=[c for c in ["timestamp"] if c in df.columns])

    cols = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
    df = df[cols].sort_index()
    return df.dropna()


def _download_yahoo(symbol: str, start: str, end: str, tf_str: str, proxies: Optional[dict] = None) -> pd.DataFrame:
    if not HAVE_YF:
        return pd.DataFrame()
    interval = tf_str.lower()
    try:
        df = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
            proxies=proxies or None,
        )
        if df is None or df.empty:
            return pd.DataFrame()
        df = df.rename(columns=str.lower)
        if "adj close" in df.columns:
            df = df.drop(columns=["adj close"])
        return df.dropna()
    except Exception:
        return pd.DataFrame()


def download_ohlc(symbol: str, start: str, end: str, interval: str, cfg: Optional[Config] = None) -> pd.DataFrame:
    provider = "auto"
    proxies = None
    if cfg is not None and hasattr(cfg, "data") and cfg.data is not None:
        provider = getattr(cfg.data, "provider", "auto") or "auto"
        http_proxy = getattr(cfg.data, "http_proxy", "") or ""
        https_proxy = getattr(cfg.data, "https_proxy", "") or ""
        if http_proxy or https_proxy:
            proxies = {}
            if http_proxy:
                proxies["http"] = http_proxy
            if https_proxy:
                proxies["https"] = https_proxy

    # 1) Alpaca if allowed & available
    if provider in ("auto", "alpaca") and HAVE_ALPACA_DATA and _has_alpaca_creds():
        df = _download_alpaca(symbol, start, end, interval)
        if not df.empty:
            return df

    # 2) Yahoo fallback
    if provider in ("auto", "yahoo"):
        df = _download_yahoo(symbol, start, end, interval, proxies=proxies)
        if not df.empty:
            return df

    return pd.DataFrame()


def rolling_dollar_vol(df: pd.DataFrame, win: int = 20) -> pd.Series:
    return (df["close"] * df.get("volume", 0)).rolling(win).mean()


def illiquidity_pass(df: pd.DataFrame, min_price: float, min_dollar_vol: float) -> bool:
    try:
        last = df.iloc[-1]
        if float(last["close"]) < min_price:
            return False
        if rolling_dollar_vol(df).iloc[-1] < min_dollar_vol:
            return False
    except Exception:
        return False
    return True
