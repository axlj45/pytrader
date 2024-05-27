import datetime
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import (
    GetOrdersRequest,
    GetCalendarRequest,
    LimitOrderRequest,
    StopLossRequest,
)
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce, OrderClass

from utils import localtime


class AlpacaClient:
    def __init__(self, api_key, secret_key, paper=True):
        self.client = TradingClient(api_key, secret_key, paper=paper)

    def close_order(self, order_id):
        """
        Closes an order.
        order_id: str - The ID of the order
        """
        return self.client.cancel_order_by_id(order_id)

    def get_orders(self):
        """
        Returns a list of all orders.
        """
        return self.client.get_orders()

    def get_order_by_id(self, order_id):
        """
        Returns information about a specific order.
        order_id: str - The ID of the order
        """
        return self.client.get_order_by_id(order_id)

    def get_open_orders(self):
        """
        Returns a list of all open orders.
        """
        return self.client.get_orders(GetOrdersRequest(status=QueryOrderStatus.OPEN))

    def get_positions(self):
        """
        Returns a list of all open positions.
        """
        return self.client.get_all_positions()

    def get_open_market_days_since(
        self, since: datetime.date, till: datetime.date = datetime.date.today()
    ):
        """
        Returns the open market days in the last week.
        """
        end_date = till
        start_date = since
        request = GetCalendarRequest(start=start_date, end=end_date)
        calendar = self.client.get_calendar(request)
        return [
            day.date
            for day in calendar
            if day.date.weekday() < 5 and day.open is not None
        ]

    def get_next_trade_day(self):
        """
        Returns the next open market day.
        """
        today = datetime.date.today()
        upcoming_trade_days = self.get_open_market_days_since(
            today, today + datetime.timedelta(days=10)
        )
        if len(upcoming_trade_days) > 0:
            timezone_aware_date = localtime.to_day(upcoming_trade_days[0])
            return timezone_aware_date
        return None

    def buy_with_stop_loss(
        self,
        symbol: str,
        qty: float | int,
        limit_price: float,
        stop_price: float,
        time_in_force=TimeInForce.DAY,
    ):
        request = LimitOrderRequest(
            symbol=symbol,
            qty=qty,
            limit_price=limit_price,
            side=OrderSide.BUY,
            time_in_force=time_in_force,
            Class=OrderClass.OTO,
            stop_loss=StopLossRequest(stop_price=stop_price),
        )

        response = self.client.submit_order(request)
        return response
