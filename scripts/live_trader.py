import argparse, time, random, numpy as np
from src.config import load_config
from src.logging_utils import get_logger
from src.calendar import MarketCalendar
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
    logger = get_logger("live")
    random.seed(cfg.general.seed); np.random.seed(cfg.general.seed)

    cal = MarketCalendar(cfg)
    oms = OMS(cfg, logger)
    rec = Reconciler(cfg, logger, oms)
    reporter = DailyReporter(cfg, logger, oms, rec)

    logger.info({"event": "boot", "tz": cfg.general.timezone, "bar": cfg.general.bar_timeframe})
    # Main loop (15m cadence implied by bar timeframe)
    while True:
        if not cal.is_trading_day_now():
            time.sleep(60); continue

        if cal.minutes_to_close() <= cfg.general.flatten_minutes_before_close:
            logger.info({"event": "pre_close_flatten"})
            oms.flatten_all()
            reporter.maybe_emit_daily()
            time.sleep(60)
            continue

        if not cal.is_bar_closed(cfg.general.bar_timeframe, cfg.general.bar_close_grace_sec):
            time.sleep(2); continue

        try:
            if oms.locked_out_today():
                time.sleep(10); continue

            # One trading cycle
            oms.trade_cycle()

            # Reconcile and log
            rec.run()

        except Exception as e:
            logger.exception({"event": "loop_exception", "error": str(e)})

        # Sleep a short while to avoid spin (bar cadence gates execution)
        time.sleep(2)

if __name__ == "__main__":
    main()

