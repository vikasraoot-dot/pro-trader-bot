import re
import pandas as pd
from .config import Config

_MIN_RE = re.compile(r"^(\d+)\s*[mM]$")
_HOUR_RE = re.compile(r"^(\d+)\s*[hH]$")
_DAY_RE = re.compile(r"^(\d+)\s*[dD]$")

def _parse_timeframe(tf: str) -> pd.Timedelta:
    """
    Parse timeframe strings like '15m', '60m', '90m', '1h', '2h', '1d' into Timedelta.
    Works for any positive integer minutes/hours/days – no 1..59 minute restriction.
    """
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
    # Fallbacks for common aliases
    if s.lower() in ("1d", "d", "day", "daily"):
        return pd.Timedelta(days=1)
    if s.lower() in ("1h", "h", "hour", "hourly"):
        return pd.Timedelta(hours=1)
    if s.lower() in ("1m", "m", "min", "minute"):
        return pd.Timedelta(minutes=1)
    raise ValueError(f"Unrecognized timeframe: {tf}")


def _floor_timestamp(ts: pd.Timestamp, step: pd.Timedelta) -> pd.Timestamp:
    """
    Floor a timezone-aware timestamp to the lower multiple of `step`,
    without relying on pandas 'M/H' alias limitations.
    """
    # Convert to UTC for integer arithmetic
    ts_utc = ts.tz_convert("UTC")
    # integer nanoseconds
    t_ns = ts_utc.value
    step_ns = int(step / pd.Timedelta(nanoseconds=1))
    floored_ns = (t_ns // step_ns) * step_ns
    floored_utc = pd.Timestamp(floored_ns, tz="UTC")
    return floored_utc.tz_convert(ts.tz)


class MarketCalendar:
    """
    Minimal calendar (dependency-free):
      - Trading days: Mon–Fri
      - RTH window: 09:30–16:00 America/New_York
      - Bar-closure detection supports arbitrary minute/hour/day frames (e.g., 15m, 60m, 90m, 1h, 2h, 1d)
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.tz = self.cfg.general.timezone

    def _now(self) -> pd.Timestamp:
        return pd.Timestamp.now(tz=self.tz)

    def is_trading_day_now(self) -> bool:
        now = self._now()
        if now.weekday() > 4:  # Sat/Sun
            return False
        rth_start = now.tz_localize(None).replace(hour=9, minute=30, second=0, microsecond=0)
        rth_end = now.tz_localize(None).replace(hour=16, minute=0, second=0, microsecond=0)
        rth_start = pd.Timestamp(rth_start, tz=self.tz)
        rth_end = pd.Timestamp(rth_end, tz=self.tz)
        return rth_start <= now <= rth_end

    def minutes_to_close(self) -> int:
        now = self._now()
        rth_end = now.tz_localize(None).replace(hour=16, minute=0, second=0, microsecond=0)
        rth_end = pd.Timestamp(rth_end, tz=self.tz)
        return max(0, int((rth_end - now).total_seconds() // 60))

    def is_bar_closed(self, timeframe: str, grace_sec: int) -> bool:
        """
        Return True if the current bar for given timeframe is closed, with `grace_sec` padding.
        Works with e.g. '15m', '60m', '90m', '1h', '2h', '1d'.
        """
        now = self._now()
        step = _parse_timeframe(timeframe)
        slot_end = _floor_timestamp(now, step)
        # The bar that started at slot_end is considered closed after slot_end + step + grace
        bar_close_time = slot_end + step + pd.Timedelta(seconds=grace_sec)
        return now >= bar_close_time