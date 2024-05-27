from google.cloud import firestore


class TraderDatabase:
    _order_collection = "orders"
    _position_collection = "positions"
    _trade_collection = "trades"

    def __init__(self):
        self.db = firestore.Client()

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
    
    def get_trade_by_signal(self, signal_key):
        """
        Retrieves the first trade that was triggered by a specific signal.
        signal_key: str - The key of the signal
        """
        trades = self.db.collection(self._trade_collection)
        query = trades.where('open_signal', '==', signal_key)
        results = query.stream()

        # Return the first result, or None if there are no results
        for doc in results:
            return doc.to_dict()
        return None