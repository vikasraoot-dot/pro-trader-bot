import time
import os
from typing import Dict, List, Any, Optional
import pandas as pd

from .config import Config
from .logging_utils import get_logger
from .broker.alpaca import AlpacaBroker
from .strategy import compute_signals, Signal
from .data import download_ohlc, illiquidity_pass
from .regime import compute_htf_regime
from .risk import position_size
from .portfolio import enforce_portfolio_limits
from .utils import gen_coid, read_tickers_file


class OMS:
    """
    Orchestrates a single trading cycle:
      - fetch OHLC for tickers
      - filter liquidity
      - compute signals
      - optional HTF alignment
      - size & place orders
    Returns a dict with candidates, orders, positions, and skipped symbols.
    """

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

    def trade_cycle(self, verbose_symbol_logs: bool = False, tickers_override: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute 1 cycle and return details for logging:
        {
          "scanned": [ { symbol, stage, note, extra? }, ... ],
          "skipped": [ "SYM", ... ],
          "candidates": [ "SYM", ... ],
          "orders": [ {symbol, qty, entry, tp, sl, coid}, ... ],
          "positions": [ "SYM", ... ]
        }
        """
        today = pd.Timestamp.utcnow().strftime("%Y-%m-%d")
        start = (pd.Timestamp.utcnow() - pd.Timedelta(days=90)).strftime("%Y-%m-%d")
        interval = self._bar_interval_str()

        tickers = tickers_override if tickers_override is not None else read_tickers_file("tickers.txt")
        tickers = [t.strip().upper() for t in tickers if t.strip()]

        scanned_log: List[Dict[str, Any]] = []
        skipped_syms: List[str] = []

        df_cache: Dict[str, pd.DataFrame] = {}
        candidates: List[str] = []

        # 1) Fetch & liquidity screen
        for sym in tickers:
            if sym in self.cfg.universe.exclude:
                skipped_syms.append(sym)
                if verbose_symbol_logs:
                    scanned_log.append({"symbol": sym, "stage": "excluded", "note": "in exclude list"})
                continue

            df = self._fetch(sym, start, today, interval)
            if df.empty:
                skipped_syms.append(sym)
                if verbose_symbol_logs:
                    scanned_log.append({"symbol": sym, "stage": "fetch", "note": "empty_data"})
                continue

            df_cache[sym] = df

            if not illiquidity_pass(df, self.cfg.universe.min_price, self.cfg.universe.min_dollar_vol_20d):
                skipped_syms.append(sym)
                if verbose_symbol_logs:
                    last_close = float(df["close"].iloc[-1])
                    scanned_log.append(
                        {
                            "symbol": sym,
                            "stage": "liquidity_fail",
                            "note": "min_price/min_dollar_vol failed",
                            "last_close": last_close,
                        }
                    )
                continue

            if verbose_symbol_logs:
                scanned_log.append({"symbol": sym, "stage": "liquidity_pass"})
            candidates.append(sym)

        # 2) Signal computation
        long_syms: List[str] = []
        for sym in candidates:
            sigs = compute_signals(df_cache[sym], self.cfg)
            if sigs.iloc[-1] == Signal.LONG:
                long_syms.append(sym)
                if verbose_symbol_logs:
                    scanned_log.append({"symbol": sym, "stage": "signal_long"})
            else:
                if verbose_symbol_logs:
                    scanned_log.append({"symbol": sym, "stage": "signal_none"})

        # 3) HTF alignment (optional)
        if self.cfg.strategy.htf_align_required:
            aligned = []
            for sym in long_syms:
                htf = self._fetch(sym, start, today, self.cfg.general.htf_timeframe)
                if htf.empty:
                    if verbose_symbol_logs:
                        scanned_log.append({"symbol": sym, "stage": "htf_missing"})
                    continue
                trend, chop = compute_htf_regime(htf, self.cfg.regime.trend_adx_min, self.cfg.regime.chop_adx_max)
                if trend.iloc[-1] and not chop.iloc[-1]:
                    aligned.append(sym)
                    if verbose_symbol_logs:
                        scanned_log.append({"symbol": sym, "stage": "htf_aligned"})
                else:
                    if verbose_symbol_logs:
                        scanned_log.append({"symbol": sym, "stage": "htf_blocked"})
            long_syms = aligned

        # 4) Portfolio/risk constraints
        equity = self.broker.account_equity()
        open_pos = self.broker.positions()
        filtered_syms = enforce_portfolio_limits(self.cfg, open_pos, long_syms, equity)

        # 5) Cooloff
        now = time.time()
        filtered_syms = [s for s in filtered_syms if self._symbol_cooloff.get(s, 0) < now]

        # 6) Place orders
        orders: List[Dict[str, Any]] = []
        for sym in filtered_syms:
            df = df_cache[sym]
            last_price = float(df["close"].iloc[-1])
            plan = position_size(self.cfg, df, last_price, equity)
            if plan.qty <= 0:
                if verbose_symbol_logs:
                    scanned_log.append({"symbol": sym, "stage": "sizing_zero", "note": "qty<=0"})
                continue

            coid = gen_coid(
                sym,
                pd.Timestamp.utcnow().strftime("%Y%m%d%H%M"),
                f"{sym}|{last_price}|{plan.qty}|{plan.stop_price}|{plan.take_profit}",
            )

            try:
                self.broker.submit_bracket(
                    symbol=sym,
                    qty=plan.qty,
                    side="buy",
                    entry_price=last_price,
                    take_profit=plan.take_profit,
                    stop_price=plan.stop_price,
                    client_order_id=coid,
                )
                orders.append(
                    {
                        "symbol": sym,
                        "qty": int(plan.qty),
                        "entry": float(last_price),
                        "tp": float(plan.take_profit),
                        "sl": float(plan.stop_price),
                        "coid": coid,
                    }
                )
                self.logger.info(
                    {
                        "event": "order_submitted",
                        "symbol": sym,
                        "qty": plan.qty,
                        "entry": last_price,
                        "tp": plan.take_profit,
                        "sl": plan.stop_price,
                        "coid": coid,
                    }
                )
                # optional cooloff to avoid immediate re-entry
                self._symbol_cooloff[sym] = time.time() + self.cfg.risk.symbol_cooloff_min * 60
            except Exception as e:
                self.logger.error({"event": "order_error", "symbol": sym, "error": str(e)})

        # 7) Build return payload
        result = {
            "scanned": scanned_log,
            "skipped": skipped_syms,
            "candidates": long_syms,        # pre-portfolio filters list of LONG signals (post-htf)
            "orders": orders,
            "positions": list(self.broker.positions().keys()),
        }

        # Optional concise summary line for humans
        self.logger.info(
            {
                "event": "cycle_summary",
                "scanned": len(scanned_log),
                "liquid_candidates": len(candidates),
                "signal_longs": len(long_syms),
                "orders": len(orders),
                "positions_open": len(result["positions"]),
            }
        )

        # Emit per-symbol logs if requested
        if verbose_symbol_logs:
            for rec in scanned_log:
                # one record per symbol stage
                self.logger.info({"event": "symbol_check", **rec})

        return result

    def flatten_all(self):
        for sym in list(self.broker.positions().keys()):
            self.broker.close_position(sym)
        self.broker.cancel_all()