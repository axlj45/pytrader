from datetime import datetime
from utils import localtime


class SignalModel:
    def __init__(
        self,
        id: str,
        symbol: str,
        action: str,
        date: datetime,
        strategy: str,
        metadata: dict | None = None,
        execute_on: datetime | None = None,
        order_id: str | None = None,
    ):
        self.id = id
        self.symbol = symbol
        self.action = action
        self.date = date
        self.strategy = strategy
        self.metadata = metadata
        self.execute_on = execute_on
        self.orderId = order_id

    def to_dict(self):
        result = {
            "symbol": self.symbol,
            "action": self.action,
            "date": self.date,
            "strategy": self.strategy,
            "executeOn": self.execute_on,
            "orderId": self.orderId,
            "metadata": self.metadata or {},
        }

        return result

    @staticmethod
    def from_dict(id, data):
        return SignalModel(
            id,
            data["symbol"],
            data["action"],
            data["date"],
            data["strategy"],
            data["metadata"],
            data["executeOn"],
            data["orderId"],
        )

    @staticmethod
    def create_signal(
        symbol,
        id: str,
        action: str,
        strategy: str,
        metadata: dict,
        execute_on: datetime,
    ):
        date = localtime.today()
        return SignalModel(
            id, symbol, action, date, strategy, metadata, execute_on=execute_on
        )
