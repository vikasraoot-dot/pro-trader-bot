import argparse
from src.config import load_config
from src.logging_utils import get_logger
from src.oms import OMS
from src.reconcile import Reconciler
from src.report import DailyReporter

def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    return p.parse_args()

def main():
    args = parse_args()
    cfg = load_config(args.config)
    logger = get_logger("report")
    oms = OMS(cfg, logger)
    rec = Reconciler(cfg, logger, oms)
    reporter = DailyReporter(cfg, logger, oms, rec)
    reporter.emit_daily(always=True)

if __name__ == "__main__":
    main()

