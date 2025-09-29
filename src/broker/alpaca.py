import os, math, time
from typing import Dict, Any, List
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest, TakeProfitRequest, StopLossRequest
from alpaca.trading.enums import OrderSide, TimeInForce
# Data client imports shown for completeness (not used in this snippet)
# from alpaca.data.historical import StockHistoricalDataClient
# from alpaca.data.requests import StockBarsRequest
# from alpaca.data.timeframe import TimeFrame

from .base import BrokerBase

def _time_in_force(tif: str):
    tif = tif.lower()
    return TimeInForce.DAY if tif == "day" else TimeInForce.DAY

def _env(name: str, default: str = "") -> str:
    v = os.getenv(name, "")
    return v if v is not None else default

def _read_alpaca_credentials():
    """
    Support both your naming (ALPACA_KEY/ALPACA_SECRET) and the common APCA_* names.
    Priority:
      1) ALPACA_KEY / ALPACA_SECRET
      2) APCA_API_KEY_ID / APCA_API_SECRET_KEY
    """
    key = _env("ALPACA_KEY") or _env("APCA_API_KEY_ID")
    secret = _env("ALPACA_SECRET") or _env("APCA_API_SECRET_KEY")
    base = _env("APCA_BASE_URL", "https://paper-api.alpaca.markets")
    if not key or not secret:
        raise RuntimeError(
            "Missing Alpaca credentials. Set ALPACA_KEY and ALPACA_SECRET "
            "(or APCA_API_KEY_ID and APCA_API_SECRET_KEY) as GitHub Secrets / environment variables."
        )
    return key, secret, base

class AlpacaBroker(BrokerBase):
    def __init__(self):
        key, sec, base = _read_alpaca_credentials()
        # If base URL contains "paper", pass paper=True so TradingClient behaves accordingly
        self.tc = TradingClient(api_key=key, secret_key=sec, paper=("paper" in base.lower()))
        self.locked = False

    def account_equity(self) -> float:
        return float(self.tc.get_account().equity)

    def positions(self) -> Dict[str, float]:
        return {p.symbol: abs(float(p.market_value)) for p in self.tc.get_all_positions()}

    def open_orders(self) -> List[Dict[str, Any]]:
        return [o.dict() for o in self.tc.get_orders()]

    def submit_bracket(self, symbol: str, qty: int, side: str, entry_price: float,
                       take_profit: float, stop_price: float, client_order_id: str):
        if qty <= 0:
            return None
        side_enum = OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL
        tif = _time_in_force("day")

        # Alpaca constraint: for BUY, TP limit must be >= entry + 0.01 (the inverse for SELL)
        if side_enum == OrderSide.BUY:
            take_profit = max(take_profit, entry_price + 0.01)
        else:
            take_profit = min(take_profit, entry_price - 0.01)

        req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=side_enum,
            time_in_force=tif,
            client_order_id=client_order_id,
            take_profit=TakeProfitRequest(limit_price=round(take_profit, 2)),
            stop_loss=StopLossRequest(stop_price=round(stop_price, 2)),
        )
        try:
            return self.tc.submit_order(req)
        except Exception:
            time.sleep(0.5)
            return self.tc.submit_order(req)

    def cancel_all(self) -> None:
        self.tc.cancel_orders()

    def close_position(self, symbol: str) -> None:
        try:
            self.tc.close_position(symbol)
        except Exception:
            pass

    def recent_fills(self, limit: int = 100) -> List[Dict[str, Any]]:
        # You can implement activities/fills fetch here if you want detailed daily PnL
        return []

    def lockout_today(self) -> bool:
        return self.locked

    def set_lockout(self, v: bool):
        self.locked = v
