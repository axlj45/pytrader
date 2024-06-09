import datetime
from typing import Callable
from alpaca.trading.client import TradingClient
from alpaca.trading.stream import TradingStream
from alpaca.trading.models import TradeUpdate, Order

from alpaca.trading.requests import (
    GetOrdersRequest,
    GetCalendarRequest,
    LimitOrderRequest,
    StopLossRequest,
)
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce, OrderClass
from alpaca.common.exceptions import APIError

from pytrader.utils import localtime


class AlpacaClient:
    def __init__(self, api_key, secret_key, paper=True):
        self.api_key = api_key
        self.secret_key = secret_key
        self.paper = paper
        self.client = TradingClient(api_key, secret_key, paper=paper)

        self._streamer = None

    def account(self):
        result = self.client.get_account()
        disabled = (
            result.account_blocked or result.trading_blocked
        ) or not result.status == "ACTIVE"

        return (not disabled, result)

    def get_order_stream(
        self, trade_updates_handler: Callable[[str, dict], None]
    ) -> None:
        async def _handle_trade_update(event: TradeUpdate):
            ao = self._order_to_dict(event.order)
            await trade_updates_handler(event.event, ao)

        if trade_updates_handler:
            trade_stream_client = TradingStream(
                self.api_key, self.secret_key, self.paper
            )
            trade_stream_client.subscribe_trade_updates(_handle_trade_update)
            trade_stream_client.run()
            self._streamer = trade_stream_client
        else:
            return None

    def close_stream(self):
        if self._streamer:
            self._streamer.stop()
            self._streamer.close()

    def _order_to_dict(self, order: Order) -> dict:
        alpaca_order = {
            "id": str(order.id),
            "client_order_id": order.client_order_id,
            "created_at": localtime.convert_to_est(order.created_at),
            "updated_at": localtime.convert_to_est(order.updated_at),
            "submitted_at": localtime.convert_to_est(order.submitted_at),
            "filled_at": localtime.convert_to_est(order.filled_at)
            if order.filled_at
            else None,
            "expired_at": localtime.convert_to_est(order.expired_at)
            if order.expired_at
            else None,
            "canceled_at": localtime.convert_to_est(order.canceled_at)
            if order.canceled_at
            else None,
            "failed_at": localtime.convert_to_est(order.failed_at)
            if order.failed_at
            else None,
            "replaced_at": localtime.convert_to_est(order.replaced_at)
            if order.replaced_at
            else None,
            "replaced_by": str(order.replaced_by) if order.replaced_by else None,
            "replaces": str(order.replaces) if order.replaces else None,
            "asset_id": str(order.asset_id),
            "symbol": order.symbol,
            "asset_class": order.asset_class.name,
            "notional": order.notional,
            "qty": float(order.qty) if order.qty else None,
            "filled_qty": float(order.filled_qty) if order.filled_qty else None,
            "filled_avg_price": float(order.filled_avg_price)
            if order.filled_avg_price
            else None,
            "order_class": order.order_class.name,
            "order_type": order.order_type.name,
            "type": order.type.name,
            "side": order.side.name,
            "time_in_force": order.time_in_force.name,
            "limit_price": float(order.limit_price) if order.limit_price else None,
            "stop_price": float(order.stop_price) if order.stop_price else None,
            "status": order.status.name,
            "extended_hours": order.extended_hours,
            "legs": [self._order_to_dict(leg) for leg in order.legs]
            if order.legs
            else None,
            "trail_percent": float(order.trail_percent)
            if order.trail_percent
            else None,
            "trail_price": float(order.trail_price) if order.trail_price else None,
            "hwm": order.hwm if order.hwm else None,
        }

        alpaca_order = {k: v for k, v in alpaca_order.items() if v is not None}

        return alpaca_order

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
        return self._order_to_dict(self.client.get_order_by_id(order_id))

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

    def get_position_for(self, symbol):
        """
        Returns a list of all open positions for a specific symbol.
        """
        try:
            return self.client.get_open_position(symbol)
        except APIError as e:
            if e.code == 40410000:  # Position not found
                return None
            raise e

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
        today = localtime.today()

        upcoming_trade_days = self.get_open_market_days_since(
            today.date(), today.date() + datetime.timedelta(days=10)
        )
        if len(upcoming_trade_days) > 1:
            timezone_aware_date = localtime.to_day(upcoming_trade_days[0])
            if timezone_aware_date.date() == today.date() and today.hour > 15:
                timezone_aware_date = localtime.to_day(upcoming_trade_days[1])
            return timezone_aware_date
        return None

    def close_position(self, symbol):
        """
        Closes a position.
        symbol: str - The symbol of the position
        """
        return self.client.close_position(symbol)

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
