import pandas as pd
from .indicators import ema, adx, rsi, ema_slope_bps

class Signal:
    NONE="NONE"; LONG="LONG"; SHORT="SHORT"

def compute_signals(df15: pd.DataFrame, cfg) -> pd.Series:
    efast = ema(df15["close"], cfg.strategy.ema_fast)
    eslow = ema(df15["close"], cfg.strategy.ema_slow)
    adx_val, pdi, mdi = adx(df15, cfg.strategy.adx_len)
    r = rsi(df15["close"], cfg.strategy.rsi_len)
    slope = ema_slope_bps(efast, 3)

    longs = (efast > eslow) & (adx_val >= cfg.strategy.adx_min) & (r.between(cfg.strategy.rsi_min, cfg.strategy.rsi_max)) & (slope >= cfg.strategy.ema_slope_bps)
    # Shorts disabled by default in config
    sig = pd.Series(Signal.NONE, index=df15.index)
    sig = sig.mask(longs, Signal.LONG)
    return sig.fillna(Signal.NONE)

