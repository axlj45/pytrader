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
    status: str
    signals: list[str] | None = None
    resolved_signals: list[SignalModel] | None = None
    cost_basis: float = None
    sale_price: float = None
    revenue: float = None
    result_pct: float = None
    opened_on: datetime = None
    closed_on: datetime = None
    market_exposure: float = None
    canceled_reason: str = None

    def to_dict(self):
        result = {
            "id": self.id,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "status": self.status,
            "strategy": self.strategy,
            "signals": self.signals or [],
        }
        return result

    def to_summary_dict(self):
        return {
            "status": "closed",
            "cost_basis": self.cost_basis,
            "sale_price": self.sale_price,
            "result_pct": self.result_pct,
            "revenue": self.revenue,
            "opened_on": self.opened_on,
            "closed_on": self.closed_on,
            "market_exposure": self.market_exposure,
            "canceled_reason": self.canceled_reason,
        }

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
        return TradeModel(trade_id, symbol, timestamp, strategy, signals=signals, status="created")
