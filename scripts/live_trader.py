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

# --- timeframe helpers ---
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

    logger.info({"event": "boot", "tz": tz, "bar": bar, "grace_sec": grace, "rth_only": rth_only})

    step = _parse_timeframe(bar)
    oms = OMS(cfg, logger=logger)

    # stop after ~10 hours so the job doesn't run forever
    hard_stop_at = pd.Timestamp.now(tz=tz) + pd.Timedelta(hours=10)

    while True:
        now = pd.Timestamp.now(tz=tz)
        if now > hard_stop_at:
            logger.info({"event": "shutdown", "reason": "hard_stop_reached"})
            return 0

        # compute current bar close time