from datetime import datetime
import os
from firebase_admin import firestore, credentials, initialize_app
from google.cloud.firestore_v1.base_query import FieldFilter
import pytz

from model.trade import TradeModel


class TraderDatabase:
    _order_collection = "orders"
    _position_collection = "positions"
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
        doc_ref = trades.document(trade.trade_id)

        if doc_ref.get().exists:
            return None

        doc_ref.set(trade.to_dict())

        # Get the document that was just created
        created_trade = doc_ref.get().to_dict()

        return TradeModel(
            created_trade["tradeId"],
            created_trade["symbol"],
            created_trade["timestamp"],
            created_trade["strategy"],
            created_trade["executeOn"],
            created_trade["signals"],
            created_trade["orderId"],
        )

    def get_trade(self, trade_id) -> TradeModel | None:
        """
        Retrieves a trade from the database.
        trade_id: str - The ID of the trade
        """
        try:
            trades = self.db.collection(self._trade_collection)
            doc_ref = trades.document(trade_id)
            trade_doc = doc_ref.get().to_dict()

            return TradeModel(
                trade_doc["symbol"],
                trade_doc["timestamp"],
                trade_doc["strategy"],
                trade_doc["signals"],
                trade_doc["orderId"],
            )
        except firestore.exceptions.NotFound:
            return None

    def get_pending_trades(self):
        """
        Retrieves all pending trades from the database.
        """
        trades = self.db.collection(self._trade_collection)
        # trades where executeOn is today and orderId is None
        today = datetime.now(pytz.timezone("US/Eastern"))
        # query = trades.where("orderId", "==", None).where("executeOn", ">=", today)
        data_filter = FieldFilter("executeOn", ">=", today)
        order_filter = FieldFilter("orderId", "==", None)
        query = trades.where(filter=data_filter).where(filter=order_filter)
        results = query.stream()

        return [TradeModel.from_dict(doc.to_dict()) for doc in results]

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
