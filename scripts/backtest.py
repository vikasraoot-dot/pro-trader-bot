import argparse, random, numpy as np
from pathlib import Path
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

def main():
    args = parse_args()
    cfg = load_config(args.config)
    logger = get_logger("backtest")

    random.seed(cfg.general.seed)
    np.random.seed(cfg.general.seed)

    # Always read from tickers.txt (with env/default fallback inside util)
    tickers = read_tickers_file("tickers.txt")

    outdir = Path(cfg.reporting.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    engine = BacktestEngine(cfg, logger)
    equity_curve, trade_log = engine.run(tickers, args.start, args.end)

    report = summarize_metrics(equity_curve, trade_log)
    report_path = outdir / "backtest_report.txt"
    report_path.write_text(report)
    logger.info({"event": "backtest_complete", "tickers": tickers, "report": str(report_path)})

    print("\n=== Backtest Report ===\n")
    print(report)

if __name__ == "__main__":
    main()
