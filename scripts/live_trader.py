import argparse
import sys
import traceback
import pandas as pd

from src.config import load_config
from src.logging_utils import get_logger
from src.calendar import MarketCalendar
from src.oms import OMS


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--config", required=True)
    return p.parse_args()


def main():
    args = parse_args()
    cfg = load_config(args.config)
    logger = get_logger("live")

    tz = cfg.general.timezone
    bar = cfg.general.bar_timeframe
    grace = cfg.general.bar_close_grace_sec
    rth_only = bool(getattr(cfg.general, "rth_only", True))

    logger.info({"event": "boot", "tz": tz, "bar": bar})

    cal = MarketCalendar(cfg)
    now = pd.Timestamp.now(tz=tz)

    # 1) Trading day / RTH gating
    if rth_only and not cal.is_trading_day_now():
        logger.info({"event": "skip", "reason": "market_closed_rth", "now": str(now)})
        return 0

    # 2) Closed-bar gating
    if not cal.is_bar_closed(bar, grace):
        logger.info({"event": "skip", "reason": "bar_not_closed", "now": str(now), "bar": bar, "grace_sec": grace})
        return 0

    # 3) Run one trading cycle
    try:
        oms = OMS(cfg, logger=logger)
        result = oms.trade_cycle()

        # We expect OMS.trade_cycle() to return a dict or object like:
        # {
        #   "candidates": [...],
        #   "orders": [...],
        #   "positions": [...]
        # }
        # If not, adjust accordingly.
        candidates = result.get("candidates", []) if isinstance(result, dict) else []
        orders = result.get("orders", []) if isinstance(result, dict) else []
        positions = result.get("positions", []) if isinstance(result, dict) else []

        logger.info(
            {
                "event": "cycle_done",
                "candidates_found": len(candidates),
                "orders_placed": len(orders),
                "open_positions": len(positions),
            }
        )

    except Exception as e:
        logger.error({"event": "loop_exception", "error": str(e)})
        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())