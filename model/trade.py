from datetime import datetime
import pytz


class TradeModel:
    def __init__(
        self,
        id: str,
        symbol: str,
        timestamp: datetime,
        strategy: str,
        signals: list[str] | None = None,
    ):
        self.id = id
        self.symbol = symbol
        self.timestamp = timestamp
        self.strategy = strategy
        self.signals = signals

    def to_dict(self):
        result = {
            "id": self.id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "strategy": self.strategy,
            "signals": self.signals or [],
        }

        return result

    @staticmethod
    def from_dict(data):
        return TradeModel(
            data["id"],
            data["symbol"],
            data["timestamp"],
            data["strategy"],
            data["signals"],
        )

    @staticmethod
    def create_trade(symbol, trade_id: str, strategy: str, signals: list[str]):
        timestamp = datetime.now(pytz.timezone("US/Eastern"))
        return TradeModel(trade_id, symbol, timestamp, strategy, signals=signals)
