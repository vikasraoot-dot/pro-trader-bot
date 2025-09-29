import math
from typing import List, Tuple, Dict, Any
import pandas as pd

from ..config import Config
from ..data import download_ohlc, illiquidity_pass
from ..strategy import compute_signals, Signal
from ..indicators import atr
from ..risk import estimate_spread_bps


def _max_drawdown(series: pd.Series) -> float:
    """Return max drawdown as a negative fraction, e.g., -0.12 for -12%."""
    if series.empty:
        return 0.0
    roll_max = series.cummax()
    dd = series / roll_max - 1.0
    return float(dd.min()) if len(dd) else 0.0


def _sharpe_from_equity(
    eq: pd.Series,
    bars_per_day: int = 26,   # ~15m bars per regular session
    trading_days: int = 252,
) -> float:
    """Annualized Sharpe from equity curve."""
    if eq is None or eq.empty or eq.iloc[0] == 0:
        return 0.0
    rets = eq.pct_change().fillna(0.0)
    vol = float(rets.std())
    if vol == 0.0:
        return 0.0
    scale = math.sqrt(bars_per_day * trading_days)
    return float(rets.mean() / vol * scale)


def _profit_factor_from_R(trade_log: pd.DataFrame) -> float:
    if trade_log is None or trade_log.empty or "R" not in trade_log.columns:
        return 0.0
    pos = float(trade_log.loc[trade_log["R"] > 0, "R"].sum())
    neg = float(trade_log.loc[trade_log["R"] < 0, "R"].sum())
    return pos / abs(neg) if neg != 0 else (pos if pos > 0 else 0.0)


def _hitrate_from_R(trade_log: pd.DataFrame) -> float:
    if trade_log is None or trade_log.empty or "R" not in trade_log.columns:
        return 0.0
    wins = int((trade_log["R"] > 0).sum())
    total = int(len(trade_log))
    return wins / total if total > 0 else 0.0


class BacktestEngine:
    def __init__(self, cfg: Config, logger):
        self.cfg = cfg
        self.logger = logger

    def simulate_symbol(self, sym: str, start: str, end: str) -> Tuple[pd.Series, pd.DataFrame]:
        """
        Returns:
          equity_curve (Series, base=1.0),
          trade_log (DataFrame with columns: side, entry, exit, R)
        """
        df = download_ohlc(sym, start, end, "15m", self.cfg)
        if df.empty or not illiquidity_pass(df, self.cfg.universe.min_price, self.cfg.universe.min_dollar_vol_20d):
            return pd.Series(dtype=float), pd.DataFrame()

        sig = compute_signals(df, self.cfg)

        a = atr(df, 14)
        a = a.bfill().ffill()

        # Hook retained for later enhancements
        _ = estimate_spread_bps(df)

        eq = [1.0]
        pos = 0
        entry = 0.0
        stop = 0.0
        tp = 0.0
        trades = []

        for i in range(1, len(df)):
            bar = df.iloc[i]
            price_open = float(bar["open"])
            price_high = float(bar["high"])
            price_low = float(bar["low"])

            # Manage existing position
            if pos > 0:
                if price_high >= tp:
                    r = (tp - entry) / (entry - stop)
                    eq.append(eq[-1] * (1 + r * 0.01))
                    trades.append({"side": "long", "entry": entry, "exit": tp, "R": r})
                    pos = 0
                elif price_low <= stop:
                    r = (stop - entry) / (entry - stop)
                    eq.append(eq[-1] * (1 + r * 0.01))
                    trades.append({"side": "long", "entry": entry, "exit": stop, "R": r})
                    pos = 0
                else:
                    eq.append(eq[-1])
            else:
                eq.append(eq[-1])

            # New entries on prior bar signal to avoid look-ahead
            if pos == 0 and sig.iloc[i - 1] == Signal.LONG:
                entry = price_open * (1 + (self.cfg.risk.slippage_bps + self.cfg.risk.commission_bps) * 1e-4)
                stop = entry - self.cfg.risk.atr_k_stop * float(a.iloc[i - 1])
                tp = entry + self.cfg.risk.take_profit_R * (entry - stop)
                pos = 1

        equity_curve = pd.Series(eq, index=df.index[: len(eq)])
        trade_log = pd.DataFrame(trades)
        return equity_curve, trade_log

    def run(
        self, tickers: List[str], start: str, end: str
    ) -> Tuple[pd.Series, pd.DataFrame, Dict[str, Dict[str, Any]]]:
        """
        Returns:
          eq_total: portfolio equity (mean of per-symbol equity, base=1.0)
          trade_log: concatenated trade logs with `symbol`
          per_symbol: dict[symbol] -> metrics dict
        """
        curves: List[pd.Series] = []
        logs: List[pd.DataFrame] = []
        per_symbol: Dict[str, Dict[str, Any]] = {}

        for sym in tickers:
            eq, tl = self.simulate_symbol(sym, start, end)

            # Per-symbol metrics
            if not eq.empty:
                net_pnl = float(eq.iloc[-1] - 1.0)
                sharpe = _sharpe_from_equity(eq)
                mdd = _max_drawdown(eq)
                pf = _profit_factor_from_R(tl)
                hr = _hitrate_from_R(tl)
                trades = int(len(tl)) if tl is not None else 0

                per_symbol[sym] = {
                    "trades": trades,
                    "net_pnl": net_pnl,
                    "hitrate": hr,
                    "profit_factor": pf,
                    "sharpe": sharpe,
                    "maxdd": mdd,
                }
                curves.append(eq.rename(sym))

            if tl is not None and not tl.empty:
                tl = tl.copy()
                tl["symbol"] = sym
                logs.append(tl)

        if curves:
            aligned = pd.concat(curves, axis=1).ffill().fillna(1.0)
            eq_total = aligned.mean(axis=1)
        else:
            eq_total = pd.Series(dtype=float)

        trade_log = pd.concat(logs, ignore_index=True) if logs else pd.DataFrame()
        return eq_total, trade_log, per_symbol
