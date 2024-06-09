from dataclasses import dataclass
from datetime import datetime
import pytz

from pytrader.model import SignalModel


@dataclass
class TradeModel:
    id: str
    symbol: str
    timestamp: datetime
    strategy: str
    signals: list[str] | None = None
    resolved_signals: list[SignalModel] | None = None

    def to_dict(self):
        result = {
            "id": self.id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "strategy": self.strategy,
            "signals": self.signals or [],
        }

        return result

    def load_signals(self):
        if self.signals is None or len(self.signals) == 0:
            return None

        self.resolved_signals = []
        for signal in self.signals:
            doc = signal.get()
            self.resolved_signals.append(SignalModel(signal.id, **doc.to_dict()))

    @staticmethod
    def create_trade(symbol, trade_id: str, strategy: str, signals: list[str]):
        timestamp = datetime.now(pytz.timezone("US/Eastern"))
        return TradeModel(trade_id, symbol, timestamp, strategy, signals=signals)
