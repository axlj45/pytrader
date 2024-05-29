import os
from firebase_admin import firestore, credentials, initialize_app
from google.cloud.firestore_v1.base_query import FieldFilter
from model.signal import SignalModel
from utils import localtime

from model.trade import TradeModel


class TraderDatabase:
    _order_collection = "orders"
    _signals_collection = "signals"
    _trade_collection = "trades"

    def __init__(self):
        cred = credentials.Certificate(os.getenv("firebase_creds"))
        initialize_app(cred)
        self.db = firestore.client()

    def add_order(self, order_data):
        collection = self.db.collection(self._order_collection)
        collection.add(order_data)

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

            return TradeModel(
                trade_id,
                trade_doc["symbol"],
                trade_doc["timestamp"],
                trade_doc["strategy"],
                trade_doc["signals"],
            )
        except Exception as e:
            print(e)
            return None

    def update_trade(self, trade_id: str, trade_data: dict):
        """
        Adds a signal to a trade in the database.
        signal_data: dict - The data to add
        """
        trades = self.db.collection(self._trade_collection)
        doc_ref = trades.document(trade_id)
        doc_ref.update(trade_data)

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
        except firestore.exceptions.NotFound:
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

        return [SignalModel.from_dict(doc.id, doc.to_dict()) for doc in results]

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
            return TradeModel.from_dict(doc.to_dict())
        return None
