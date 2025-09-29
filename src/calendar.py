import pandas as pd
from .config import Config

class MarketCalendar:
    """
    Minimal calendar:
    - RTH: Mon–Fri, 09:30–16:00 America/New_York
    - Bar closure: grace-seconds past last timeframe boundary
    This avoids external calendar dependencies on the Windows runner.
    """

    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.tz = self.cfg.general.timezone

    def _now(self) -> pd.Timestamp:
        return pd.Timestamp.now(tz=self.tz)

    def is_trading_day_now(self) -> bool:
        now = self._now()
        if now.weekday() > 4:
            return False
        start = now.tz_localize(None).replace(hour=9, minute=30, second=0, microsecond=0)
        end = now.tz_localize(None).replace(hour=16, minute=0, second=0, microsecond=0)
        start = pd.Timestamp(start, tz=self.tz)
        end = pd.Timestamp(end, tz=self.tz)
        return start <= now <= end

    def minutes_to_close(self) -> int:
        now = self._now()
        end = now.tz_localize(None).replace(hour=16, minute=0, second=0, microsecond=0)
        end = pd.Timestamp(end, tz=self.tz)
        return max(0, int((end - now).total_seconds() // 60))

    def is_bar_closed(self, timeframe: str, grace_sec: int) -> bool:
        now = self._now()
        if not timeframe.endswith("m"):
            return True
        m = int(timeframe[:-1])
        slot_end = now.floor(f"{m}min")
        return now >= slot_end + pd.Timedelta(seconds=grace_sec)
