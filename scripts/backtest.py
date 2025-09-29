import argparse
import random
from pathlib import Path
from typing import Dict, Any, List

import numpy as np

from src.config import load_config
from src.logging_utils import get_logger
from src.backtest.engine import BacktestEngine
from src.backtest.metrics import summarize_metrics
from src.utils import read_tickers_file


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    p.add_argument("--start", required=True)
    p.add_argument("--end", required=True)
    return p.parse_args()


def _format_pct(x: float, digits: int = 2) -> str:
    return f"{x * 100:.{digits}f}%"


def _render_per_symbol_table(per_symbol: Dict[str, Dict[str, Any]]) -> str:
    if not per_symbol:
        return "No per-symbol results.\n"

    # Sort by net PnL descending
    items = sorted(per_symbol.items(), key=lambda kv: kv[1].get("net_pnl", 0.0), reverse=True)

    # Header
    lines: List[str] = []
    lines.append(f"{'Symbol':<8} {'Trades':>7} {'NetPnL':>10} {'HitRate':>9} {'PF':>6} {'Sharpe':>8} {'MaxDD':>9}")

    # Rows
    for sym, m in items:
        trades = m.get("trades", 0)
        net_pnl = _format_pct(m.get("net_pnl", 0.0))
        hitrate = _format_pct(m.get("hitrate", 0.0))
        pf = m.get("profit_factor", 0.0)
        sharpe = m.get("sharpe", 0.0)
        maxdd = _format_pct(m.get("maxdd", 0.0))  # negative number shown as -xx.xx%

        lines.append(
            f"{sym:<8} {trades:>7d} {net_pnl:>10} {hitrate:>9} {pf:>6.2f} {sharpe:>8.2f} {maxdd:>9}"
        )

    return "\n".join(lines) + "\n"


def main():
    args = parse_args()
    cfg = load_config(args.config)
    logger = get_logger("backtest")

    random.seed(cfg.general.seed)
    np.random.seed(cfg.general.seed)

    # Always read from tickers.txt (utils handles env/default fallbacks)
    tickers = read_tickers_file("tickers.txt")

    outdir = Path(cfg.reporting.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    engine = BacktestEngine(cfg, logger)
    equity_curve, trade_log, per_symbol = engine.run(tickers, args.start, args.end)

    # Portfolio-level summary (existing function)
    portfolio_report = summarize_metrics(equity_curve, trade_log)

    # Per-symbol table
    per_symbol_section = _render_per_symbol_table(per_symbol)

    # Compose final report
    report = (
        portfolio_report
        + "\n"
        + "--- Per Ticker Performance ---\n"
        + per_symbol_section
    )

    report_path = outdir / "backtest_report.txt"
    report_path.write_text(report)
    logger.info({"event": "backtest_complete", "tickers": tickers, "report": str(report_path)})

    print("\n=== Backtest Report ===\n")
    print(report)


if __name__ == "__main__":
    main()
