import argparse
import sys
import time
import traceback
import re
import pandas as pd

from src.config import load_config
from src.logging_utils import get_logger
from src.oms import OMS
from src.utils import read_tickers_file


# --- local timeframe helpers (independent from calendar.py internals) ---
_MIN_RE = re.compile(r"^(\d+)\s*[mM]$")
_HOUR_RE = re.compile(r"^(\d+)\s*[hH]$")
_DAY_RE = re.compile(r"^(\d+)\s*[dD]$")

def _parse_timeframe(tf: str) -> pd.Timedelta:
    s = tf.strip()
    m = _MIN_RE.match(s)
    if m:
        n = int(m.group(1))
        if n <= 0:
            raise ValueError("Minute timeframe must be > 0")
        return pd.Timedelta(minutes=n)
    h = _HOUR_RE.match(s)
    if h:
        n = int(h.group(1))
        if n <= 0:
            raise ValueError("Hour timeframe must be > 0")
        return pd.Timedelta(hours=n)
    d = _DAY_RE.match(s)
    if d:
        n = int(d.group(1))
        if n <= 0:
            raise ValueError("Day timeframe must be > 0")
        return pd.Timedelta(days=n)
    if s.lower() in ("1d", "d", "day", "daily"):
        return pd.Timedelta(days=1)
    if s.lower() in ("1h", "h", "hour", "hourly"):
        return pd.Timedelta(hours=1)
    if s.lower() in ("1m", "m", "min", "minute"):
        return pd.Timedelta(minutes=1)
    raise ValueError(f"Unrecognized timeframe: {tf}")

def _floor_timestamp(ts: pd.Timestamp, step: pd.Timedelta) -> pd.Timestamp:
    ts_utc = ts.tz_convert("UTC")
    t_ns = ts_utc.value
    step_ns = int(step / pd.Timedelta(nanoseconds=1))
    floored_ns = (t_ns // step_ns) * step_ns
    floored_utc = pd.Timestamp(floored_ns, tz="UTC")
    return floored_utc.tz_convert(ts.tz)


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
    grace = int(cfg.general.bar_close_grace_sec)
    rth_only = bool(getattr(cfg.general, "rth_only", True))

    # Boot banner
    logger.info({"event": "boot", "tz": tz, "bar": bar, "grace_sec": grace, "rth_only": rth_only})

    # Long-lived loop: from now until market close (or 16:10 ET if rth_only)
    # We wake right after each bar closes.
    step = _parse_timeframe(bar)

    # OMS instance (reused across cycles)
    oms = OMS(cfg, logger=logger)

    # simple guard to avoid infinite runs overnight: stop after ~8.5h of RTH + buffer
    hard_stop_at = pd.Timestamp.now(tz=tz) + pd.Timedelta(hours=10)

    while True:
        now = pd.Timestamp.now(tz=tz)
        if now > hard_stop_at:
            logger.info({"event": "shutdown", "reason": "hard_stop_reached"})
            return 0

        # compute current/next bar close time
        slot_start = _floor_timestamp(now, step)
        bar_close_time = slot_start + step + pd.Timedelta(seconds=grace)

        # if we woke before close, sleep until close (with 1s buffer loop)
        if now < bar_close_time:
            # one-time message at start of sleep
            sleep_sec = max(1, int((bar_close_time - now).total_seconds()))
            logger.debug({"event": "sleep_until_close", "wake_at": str(bar_close_time), "sleep_sec": sleep_sec})
            # sleep in small chunks so job can be cancelled quickly
            remaining = sleep_sec
            while remaining > 0:
                t = min(5, remaining)
                time.sleep(t)
                remaining -= t
            continue

        # bar is closed -> run one trade cycle
        try:
            tickers = read_tickers_file("tickers.txt")
            logger.info({"event": "cycle_start", "at": str(now), "tickers": tickers})

            result = oms.trade_cycle(verbose_symbol_logs=True, tickers_override=tickers)

            # Summarize
            candidates = result.get("candidates", [])
            orders = result.get("orders", [])
            positions = result.get("positions", [])
            skipped = result.get("skipped", [])  # liquidity/empty/etc.

            logger.info(
                {
                    "event": "cycle_done",
                    "at": str(pd.Timestamp.now(tz=tz)),
                    "candidates_found": len(candidates),
                    "orders_placed": len(orders),
                    "open_positions": len(positions),
                    "skipped_symbols": len(skipped),
                }
            )

        except Exception as e:
            logger.error({"event": "loop_exception", "error": str(e)})
            traceback.print_exc()
            # brief backoff then continue (don’t kill the long-lived run)
            time.sleep(5)

        # loop will compute next bar boundary and repeat

    # unreachable
    # return 0


if __name__ == "__main__":
    sys.exit(main())