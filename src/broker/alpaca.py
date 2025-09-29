import os, math, time
from typing import Dict, Any, List
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetAssetsRequest, MarketOrderRequest, TakeProfitRequest, StopLossRequest, LimitOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

from .base import BrokerBase

def _time_in_force(tif: str):
    tif = tif.lower()
    return TimeInForce.DAY if tif=="day" else TimeInForce.DAY

class AlpacaBroker(BrokerBase):
    def __init__(self):
        key = os.getenv("APCA_API_KEY_ID"); sec = os.getenv("APCA_API_SECRET_KEY")
        base = os.getenv("APCA_BASE_URL", "https://paper-api.alpaca.markets")
        if not key or not sec:
            raise RuntimeError("Missing Alpaca credentials in env.")
        self.tc = TradingClient(api_key=key, secret_key=sec, paper="paper" in base)
        self.locked = False

    def account_equity(self) -> float:
        return float(self.tc.get_account().equity)

    def positions(self) -> Dict[str, float]:
        return {p.symbol: abs(float(p.market_value)) for p in self.tc.get_all_positions()}

    def open_orders(self) -> List[Dict[str, Any]]:
        return [o.dict() for o in self.tc.get_orders()]

    def submit_bracket(self, symbol: str, qty: int, side: str, entry_price: float, take_profit: float, stop_price: float, client_order_id: str):
        # Use market entry with OCO children via Alpaca; enforce min increments
        if qty <= 0: return None
        side_enum = OrderSide.BUY if side.lower()=="buy" else OrderSide.SELL
        tif = _time_in_force("day")
        # Important: TP must be >= base_price + 0.01 for buys
        if side_enum == OrderSide.BUY:
            take_profit = max(take_profit, entry_price + 0.01)
        else:
            take_profit = min(take_profit, entry_price - 0.01)

        req = MarketOrderRequest(
            symbol=symbol, qty=qty, side=side_enum, time_in_force=tif,
            client_order_id=client_order_id,
            take_profit=TakeProfitRequest(limit_price=round(take_profit, 2)),
            stop_loss=StopLossRequest(stop_price=round(stop_price, 2))
        )
        try:
            return self.tc.submit_order(req)
        except Exception as e:
            # simple backoff retry
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
        # Alpaca trading client has get_activities; simplified omitted for brevity
        return []

    def lockout_today(self) -> bool:
        return self.locked

    def set_lockout(self, v: bool):
        self.locked = v

