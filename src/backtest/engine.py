import pandas as pd
from typing import List, Tuple
from ..config import Config
from ..data import download_ohlc, illiquidity_pass
from ..strategy import compute_signals, Signal
from ..indicators import atr
from ..risk import estimate_spread_bps

class BacktestEngine:
    def __init__(self, cfg: Config, logger):
        self.cfg = cfg
        self.logger = logger

    def simulate_symbol(self, sym: str, start: str, end: str) -> Tuple[pd.Series, pd.DataFrame]:
        df = download_ohlc(sym, start, end, "15m", self.cfg)
        if df.empty or not illiquidity_pass(df, self.cfg.universe.min_price, self.cfg.universe.min_dollar_vol_20d):
            return pd.Series(dtype=float), pd.DataFrame()

        sig = compute_signals(df, self.cfg)
        a = atr(df, 14).fillna(method="bfill").fillna(method="ffill")
        _ = estimate_spread_bps(df)  # retained hook

        eq = [1.0]; pos = 0; entry=0; stop=0; tp=0
        trades = []
        for i in range(1, len(df)):
            bar = df.iloc[i]
            price_open = float(bar["open"])
            price_high = float(bar["high"])
            price_low = float(bar["low"])

            if pos > 0:
                if price_high >= tp:
                    r = (tp - entry) / (entry - stop)
                    eq.append(eq[-1] * (1 + r * 0.01))
                    trades.append({"side":"long","entry":entry,"exit":tp,"R":r})
                    pos=0
                elif price_low <= stop:
                    r = (stop - entry) / (entry - stop)
                    eq.append(eq[-1] * (1 + r * 0.01))
                    trades.append({"side":"long","entry":entry,"exit":stop,"R":r})
                    pos=0
                else:
                    eq.append(eq[-1])
            else:
                eq.append(eq[-1])

            if pos==0 and sig.iloc[i-1]==Signal.LONG:
                entry = price_open * (1 + (self.cfg.risk.slippage_bps + self.cfg.risk.commission_bps)*1e-4)
                stop = entry - self.cfg.risk.atr_k_stop * float(a.iloc[i-1])
                tp   = entry + self.cfg.risk.take_profit_R * (entry - stop)
                pos = 1

        equity_curve = pd.Series(eq, index=df.index[:len(eq)])
        import pandas as _pd
        trade_log = _pd.DataFrame(trades)
        return equity_curve, trade_log

    def run(self, tickers: List[str], start: str, end: str) -> Tuple[pd.Series, pd.DataFrame]:
        curves = []
        logs = []
        for sym in tickers:
            eq, tl = self.simulate_symbol(sym, start, end)
            if not eq.empty:
                curves.append(eq.rename(sym))
            if not tl.empty:
                tl["symbol"] = sym
                logs.append(tl)
        if curves:
            aligned = pd.concat(curves, axis=1).fillna(method="ffill").fillna(1.0)
            eq_total = aligned.mean(axis=1)
        else:
            eq_total = pd.Series(dtype=float)
        import pandas as _pd
        trade_log = _pd.concat(logs, ignore_index=True) if logs else _pd.DataFrame()
        return eq_total, trade_log
