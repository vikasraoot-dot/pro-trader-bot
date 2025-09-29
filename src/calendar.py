import pandas_market_calendars as pmc
import pandas as pd
from datetime import datetime, timedelta
from .config import Config

class MarketCalendar:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.cal = pmc.get_calendar("XNYS")

    def _now(self) -> pd.Timestamp:
        return pd.Timestamp(datetime.now(), tz=self.cfg.general.timezone)

    def is_trading_day_now(self) -> bool:
        now = self._now()
        sched = self.cal.schedule(start_date=now.date(), end_date=now.date())
        return not sched.empty and (sched.iloc[0]["market_open"] <= now <= sched.iloc[0]["market_close"])

    def minutes_to_close(self) -> int:
        now = self._now()
        sched = self.cal.schedule(start_date=now.date(), end_date=now.date())
        if sched.empty: return 9999
        close = sched.iloc[0]["market_close"]
        return max(0, int((close - now).total_seconds() // 60))

    def is_bar_closed(self, timeframe: str, grace_sec: int) -> bool:
        # Works on 1m multiples (e.g., 15m, 60m)
        now = self._now()
        m = int(timeframe.replace("m",""))
        slot_end = now.floor(f"{m}min")
        # allow a grace period after slot_end
        return now >= slot_end + pd.Timedelta(seconds=grace_sec)

