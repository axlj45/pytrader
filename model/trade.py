from datetime import datetime

import pytz


class TradeModel:
    def __init__(
        self,
        trade_id: str,
        symbol: str,
        timestamp,
        strategy: str,
        execute_on: datetime = None,
        signals=None,
        order_id=None,
    ):
        self.trade_id = trade_id
        self.symbol = symbol
        self.timestamp = timestamp
        self.strategy = strategy
        self.execute_on = execute_on
        self.signals = signals
        self.orderId = order_id

    def to_dict(self):
        print(self.execute_on)
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "strategy": self.strategy,
            "signals": self.signals,
            "orderId": self.orderId,
            "tradeId": self.trade_id,
            "executeOn": self.execute_on,
        }

    @staticmethod
    def from_dict(data):
        return TradeModel(
            data["tradeId"],
            data["symbol"],
            data["timestamp"],
            data["strategy"],
            data["executeOn"],
            data["signals"],
            data["orderId"],
        )

    @staticmethod
    def create_trade(symbol, trade_id: str, strategy: str, execute_on: datetime):
        timestamp = datetime.now(pytz.timezone("US/Eastern"))
        return TradeModel(trade_id, symbol, timestamp, strategy, execute_on=execute_on)
