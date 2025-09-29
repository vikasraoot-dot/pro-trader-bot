import time, os
from typing import Dict
import pandas as pd
from .config import Config
from .logging_utils import get_logger
from .broker.alpaca import AlpacaBroker
from .strategy import compute_signals, Signal
from .data import download_ohlc, illiquidity_pass
from .regime import compute_htf_regime
from .risk import position_size
from .portfolio import enforce_portfolio_limits
from .utils import gen_coid

class OMS:
    def __init__(self, cfg: Config, logger=None):
        self.cfg = cfg
        self.logger = logger or get_logger("oms")
        self.broker = AlpacaBroker()
        self._daily_loss_lock = False
        self._symbol_cooloff: Dict[str, float] = {}

    def locked_out_today(self) -> bool:
        return self._daily_loss_lock or self.broker.lockout_today()

    def _bar_interval_str(self) -> str:
        return self.cfg.general.bar_timeframe

    def _fetch(self, sym: str, start: str, end: str, interval: str) -> pd.DataFrame:
        return download_ohlc(sym, start, end, interval, self.cfg)

    def trade_cycle(self):
        today = pd.Timestamp.utcnow().strftime("%Y-%m-%d")
        start = (pd.Timestamp.utcnow() - pd.Timedelta(days=90)).strftime("%Y-%m-%d")

        tickers = os.environ.get("TICKERS", "NVDA,MSFT,AMD,TSLA,AAPL").split(",")
        tickers = [t.strip().upper() for t in tickers if t.strip()]
        interval = self._bar_interval_str()

        df_cache = {}
        candidates = []
        for sym in tickers:
            if sym in self.cfg.universe.exclude:
                continue
            df = self._fetch(sym, start, today, interval)
            if df.empty:
                continue
            df_cache[sym] = df
            if illiquidity_pass(df, self.cfg.universe.min_price, self.cfg.universe.min_dollar_vol_20d):
                candidates.append(sym)

        long_symbols = []
        for sym in candidates:
            sigs = compute_signals(df_cache[sym], self.cfg)
            if sigs.iloc[-1] == Signal.LONG:
                long_symbols.append(sym)

        if self.cfg.strategy.htf_align_required:
            aligned = []
            for sym in long_symbols:
                htf = self._fetch(sym, start, today, self.cfg.general.htf_timeframe)
                if htf.empty:
                    continue
                trend, chop = compute_htf_regime(htf, self.cfg.regime.trend_adx_min, self.cfg.regime.chop_adx_max)
                if trend.iloc[-1] and not chop.iloc[-1]:
                    aligned.append(sym)
            long_symbols = aligned

        equity = self.broker.account_equity()
        open_pos = self.broker.positions()
        long_symbols = enforce_portfolio_limits(self.cfg, open_pos, long_symbols, equity)

        now = time.time()
        long_symbols = [s for s in long_symbols if self._symbol_cooloff.get(s, 0) < now]

        for sym in long_symbols:
            df = df_cache[sym]
            last_price = float(df["close"].iloc[-1])
            plan = position_size(self.cfg, df, last_price, equity)
            if plan.qty <= 0:
                continue
            coid = gen_coid(sym, pd.Timestamp.utcnow().strftime("%Y%m%d%H%M"),
                            f"{sym}|{last_price}|{plan.qty}|{plan.stop_price}|{plan.take_profit}")
            self.broker.submit_bracket(
                symbol=sym,
                qty=plan.qty,
                side="buy",
                entry_price=last_price,
                take_profit=plan.take_profit,
                stop_price=plan.stop_price,
                client_order_id=coid,
            )
            self.logger.info({"event": "order_submitted", "symbol": sym, "qty": plan.qty,
                              "entry": last_price, "tp": plan.take_profit, "sl": plan.stop_price})

    def flatten_all(self):
        for sym in list(self.broker.positions().keys()):
            self.broker.close_position(sym)
        self.broker.cancel_all()
