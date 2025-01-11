import logging as l
from firebase_admin import firestore, credentials, initialize_app
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.document import DocumentReference

from pytrader.model import TradeModel, SignalModel
from pytrader.utils import localtime, TradeConfig


class TraderDatabase:
    _order_collection = "orders"
    _signals_collection = "signals"
    _trade_collection = "trades"

    def __init__(self, cfg: TradeConfig = None):
        cred = credentials.Certificate(cfg.db_creds_path)
        initialize_app(cred)
        self.db = firestore.client()

    def upsert_order(self, order_key, order_data):
        collection = self.db.collection(self._order_collection)
        doc_ref = collection.document(order_key)
        doc_ref.set(order_data)

    def get_order(self, order_id):
        """
        Retrieves a document from the collection.
        doc_id: str - The ID of the document
        """
        collection = self.db.collection(self._order_collection)
        doc_ref = collection.document(order_id)
        return doc_ref.get().to_dict()

    def add_trade(self, trade: TradeModel) -> TradeModel | None:
        """
        Adds a trade to the database.
        trade: TradeModel - The trade to add
        """
        trades = self.db.collection(self._trade_collection)
        doc_ref = trades.document(trade.id)

        if doc_ref.get().exists:
            return None

        doc_ref.set(trade.to_dict())

        # Get the document that was just created
        created_trade = doc_ref.get().to_dict()

        return TradeModel(
            trade.id,
            created_trade["symbol"],
            created_trade["timestamp"],
            created_trade["strategy"],
            created_trade["signals"],
        )

    def get_trade(self, trade_id: str) -> TradeModel | None:
        """
        Retrieves a trade from the database.
        trade_id: str - The ID of the trade
        """
        try:
            trades = self.db.collection(self._trade_collection)
            doc_ref = trades.document(trade_id)
            trade_doc = doc_ref.get().to_dict()

            if trade_doc is None:
                return None

            if "signals" not in trade_doc:
                trade_doc["signals"] = []
            resolved_signals = []

            for signal in trade_doc["signals"]:
                if isinstance(signal, DocumentReference):
                    doc = signal.get().to_dict()
                    model = SignalModel(signal.id, **doc)
                    if doc["orderId"] is not None:
                        order = self.get_order(f'alpaca_{doc["orderId"]}')
                        if order is None:
                            order = self.get_order(f'alapca_{doc["orderId"]}')
                        model.resolvedOrder = order
                    resolved_signals.append(model)

            return TradeModel(
                id=trade_id,
                symbol=trade_doc["symbol"],
                timestamp=trade_doc["timestamp"],
                strategy=trade_doc["strategy"],
                status=trade_doc.get("status"),
                signals=trade_doc["signals"],
                resolved_signals=resolved_signals,
            )
        except Exception as e:
            l.error(e)
            return None

    def update_trade(self, trade_id: str, trade_data: dict):
        """
        Adds a signal to a trade in the database.
        signal_data: dict - The data to add
        """
        trades = self.db.collection(self._trade_collection)
        doc_ref = trades.document(trade_id)
        doc_ref.update(trade_data)

    def get_trades(self, include_closed: bool = False):
        """
        Retrieves all trades from the database.
        """
        trades = self.db.collection(self._trade_collection)
        if include_closed:
            query = trades
        else:
            data_filter = FieldFilter("status", "not-in", ["closed", "canceled"])
            query = trades.where(filter=data_filter)

        results = query.stream()
        return results
        # return [TradeModel.from_dict(doc.id, doc.to_dict()) for doc in results]

    def close_trade(self, trade: TradeModel):
        self.update_trade(trade.id, trade.to_summary_dict())

    def add_signal(self, signal: SignalModel) -> SignalModel | None:
        """
        Adds a trade to the database.
        trade: TradeModel - The trade to add
        """
        trades = self.db.collection(self._signals_collection)
        doc_ref = trades.document(signal.id)

        if doc_ref.get().exists:
            return None

        doc_ref.set(signal.to_dict())

        # Get the document that was just created
        created_signal = doc_ref.get().to_dict()

        return SignalModel(
            signal.id,
            created_signal["symbol"],
            created_signal["date"],
            created_signal["strategy"],
            created_signal["executeOn"],
        )

    def add_signal_ref_to_trade(self, trade_id: str, signal_id: str):
        """
        Adds a signal to a trade in the database.
        trade_id: str - The ID of the trade
        signal_id: str - The ID of the signal
        """
        trades = self.db.collection(self._trade_collection)
        signal = self.db.collection(self._signals_collection)
        doc_ref = trades.document(trade_id)
        signal_ref = signal.document(signal_id)

        trade = doc_ref.get().to_dict()

        if signal_ref not in trade["signals"]:
            trade["signals"].append(signal_ref)
            doc_ref.update({"signals": trade["signals"]})

    def get_signal(self, signal_id: str) -> SignalModel | None:
        """
        Retrieves a trade from the database.
        trade_id: str - The ID of the trade
        """
        try:
            trades = self.db.collection(self._signals_collection)
            doc_ref = trades.document(signal_id)
            signal_doc_ref = doc_ref.get().to_dict()

            return SignalModel(
                signal_doc_ref["id"],
                signal_doc_ref["symbol"],
                signal_doc_ref["timestamp"],
                signal_doc_ref["strategy"],
                signal_doc_ref["executeOn"],
                signal_doc_ref["orderId"],
            )
        except Exception:
            return None

    def get_pending_signals(self) -> list[SignalModel]:
        """
        Retrieves all pending trades from the database.
        """
        signals = self.db.collection(self._signals_collection)
        today = localtime.to_day(localtime.today())
        data_filter = FieldFilter("executeOn", ">=", today)
        order_filter = FieldFilter("orderId", "==", None)
        query = signals.where(filter=data_filter).where(filter=order_filter)
        results = query.stream()

        return [SignalModel(doc.id, **doc.to_dict()) for doc in results]

    def update_signal_order(self, signal_id: str, order_id: str):
        """
        Updates a trade in the database.
        signal_id: str - The ID of the signal
        order_id: dict - The data to update
        """
        signals = self.db.collection(self._signals_collection)
        doc_ref = signals.document(signal_id)
        data = {"orderId": str(order_id)}
        doc_ref.update(data)

    def get_trade_by_signal(self, signal_key) -> TradeModel:
        """
        Retrieves the first trade that was triggered by a specific signal.
        signal_key: str - The key of the signal
        """
        trades = self.db.collection(self._trade_collection)
        query = trades.where("signal", "==", signal_key)
        results = query.stream()

        # Return the first result, or None if there are no results
        for doc in results:
            return TradeModel(**doc.to_dict())
        return None
