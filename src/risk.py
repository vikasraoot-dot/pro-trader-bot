import math
from dataclasses import dataclass
from .indicators import atr
from .config import Config
import pandas as pd

@dataclass
class TradePlan:
    qty: int
    stop_price: float
    take_profit: float
    be_trigger: float
    partial_at: float
    partial_pct: float

def estimate_spread_bps(df: pd.DataFrame) -> float:
    # Rough proxy: (high-low)/close * 10,000 over last bar
    last = df.iloc[-1]
    return float((last["high"] - last["low"]) / last["close"] * 10000.0)

def position_size(cfg: Config, df: pd.DataFrame, price: float, equity: float) -> TradePlan:
    a = atr(df, 14).iloc[-1]
    spread_bps_est = estimate_spread_bps(df)
    if spread_bps_est > cfg.risk.spread_bps_max:
        return TradePlan(0,0,0,0,0,0)

    per_share_risk = max(cfg.risk.atr_k_stop * a, (cfg.risk.slippage_bps + cfg.risk.commission_bps) * price * 1e-4)
    risk_budget = equity * cfg.risk.account_risk_per_trade
    qty = int(max(0, math.floor(risk_budget / per_share_risk)))
    notional = qty * price
    if notional < cfg.risk.min_notional:
        qty = 0

    stop_price = price - cfg.risk.atr_k_stop * a
    take_profit = price + cfg.risk.take_profit_R * (price - stop_price)
    be_trigger = price + cfg.risk.be_bump_at_R * (price - stop_price)
    partial_at = price + cfg.risk.partial_take_R * (price - stop_price)
    return TradePlan(qty, stop_price, take_profit, be_trigger, partial_at, cfg.risk.partial_take_pct)

