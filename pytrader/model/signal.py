from dataclasses import dataclass
from datetime import datetime
from pytrader.utils import localtime


@dataclass
class SignalModel:
    id: str
    symbol: str
    action: str
    date: datetime
    strategy: str
    metadata: dict | None = None
    executeOn: datetime | None = None
    orderId: str | None = None
    resolvedOrder: dict | None = None

    def to_dict(self):
        result = {
            "symbol": self.symbol,
            "action": self.action,
            "date": self.date,
            "strategy": self.strategy,
            "executeOn": self.executeOn,
            "orderId": self.orderId,
            "metadata": self.metadata or {},
            "resolvedOrder": self.resolvedOrder or {},
        }
        return result

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
        return SignalModel(id, symbol, action, date, strategy, metadata, executeOn=execute_on)
