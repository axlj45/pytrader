import signal as system_signal
import sys

import click
from model.signal import SignalModel
from model.trade import TradeModel

from services.alpaca import AlpacaClient
from services.database import TraderDatabase
from services.rsi_signal_provider import rsi_signals
from utils import localtime
from utils.config import TradeConfig


@click.group()
def cli():
    pass


@cli.command()
@click.option("--live", is_flag=True, help="Execute against live account.")
@click.option("--refresh", is_flag=True, help="Force refresh of RSI signals.")
def rsi(live: bool, refresh: bool):
    """Calculate RSI signals for all tickers in the S&P 500."""
    signals_by_symbol = rsi_signals(refresh)
    cfg = TradeConfig()
    db = TraderDatabase(cfg)
    client = AlpacaClient(cfg.alpaca_key, cfg.alpaca_secret, live or cfg.alpaca_paper)

    for symbol in signals_by_symbol:
        signal_data = signals_by_symbol[symbol]
        last_signal = _df_row_to_signal(symbol, signal_data.iloc[-1])

        d = last_signal["date"]
        today = localtime.today()
        market_days = None
        key = _get_trade_key(symbol, last_signal)

        if last_signal["action"] == "Buy":
            market_days = client.get_open_market_days_since(d)
            next_trade_day = client.get_next_trade_day()

            signal = SignalModel.create_signal(
                symbol, key, "Buy", "RSI", last_signal["metadata"], next_trade_day
            )
            result = db.add_signal(signal)

            if result is None:
                print(f"BUY signal for {symbol} has already been triggered: {key}.")
                continue

            trade = TradeModel.create_trade(symbol, key, "RSI", [])
            db.add_trade(trade)
            db.add_signal_ref_to_trade(trade.id, signal.id)

            print(
                f"Buy Signal for {symbol} on {d} is {(today - d).days} days old but {len(market_days)} market days old."
            )
            print(
                f"Next trade day is {next_trade_day} which is {(next_trade_day - today).days} days away."
            )

        elif last_signal["action"] == "Sell":
            market_days = client.get_open_market_days_since(d)
            buy_signal = _df_row_to_signal(symbol, signal_data.iloc[-2])
            buy_key = _get_trade_key(symbol, buy_signal).replace("hold", "buy")

            trade = db.get_trade(buy_key)

            if trade is None:
                print(f"Close signal triggered for {symbol} but no opening trade could be located: {buy_key}.")
                continue

            open_signal = (
                trade.resolved_signals[0]
                if len(trade.resolved_signals or []) > 0
                else None
            )

            if open_signal is None:
                msg = f"Close signal triggered for {symbol} but no opening signal could be found for {buy_key}."
                print(msg)
                continue

            open_order = client.get_order_by_id(open_signal.orderId)
            if open_order is None or open_order.status not in [
                "filled",
                "partially_filled",
            ]:
                msg = f"Close signal triggered for {symbol} but no filled orders could be found for {buy_key}."
                print(msg)
                continue

            next_trade_day = client.get_next_trade_day()

            close_signal = SignalModel.create_signal(
                symbol, key, "Sell", "RSI", last_signal["metadata"], next_trade_day
            )
            result = db.add_signal(close_signal)

            if result is None:
                print(f"SELL signal for {symbol} has already been triggered: {key}.")
                continue

            db.add_signal_ref_to_trade(trade.id, close_signal.id)

            print(f"Close Signal for {symbol}")


@cli.command()
def process_signals():
    """Process RSI signals and execute trades."""
    cfg = TradeConfig()
    client = AlpacaClient(cfg.alpaca_key, cfg.alpaca_secret, cfg.alpaca_paper)
    db = TraderDatabase(cfg)
    enabled, account = client.account()
    if not enabled:
        print("Account is not enabled for trading. Exiting.")
        return

    account_value = float(account.portfolio_value)
    cash = float(account.non_marginable_buying_power)
    max_trade_value = account_value * 0.05

    print(f"Account Value: {account_value}")
    print(f"Cash: {cash}")

    signals = db.get_pending_signals()
    print(f"Processing {len(signals)} signals.")

    for signal in signals:
        symbol = signal.symbol

        if signal.action == "Buy":
            if cash < max_trade_value:
                print(f"Insufficient cash to buy {symbol}.")
                continue

            last_close_price = signal.metadata["close"]
            last_open_price = signal.metadata["open"]
            stop_price = last_close_price * 0.98

            existing_cost_basis = 0

            position = client.get_position_for(symbol)
            if position is not None:
                existing_cost_basis = float(position.avg_entry_price) * int(
                    position.qty
                )

            print(f"Existing cost basis for {symbol}: {existing_cost_basis}")
            available_symbol_funds = max_trade_value - existing_cost_basis

            qty = int(available_symbol_funds / last_close_price)
            if qty == 0:
                print(f"Insufficient funds to buy {symbol}.")
                continue

            print(f"Buying {qty} shares of {symbol} at {last_open_price}.")

            order = client.buy_with_stop_loss(symbol, qty, last_open_price, stop_price)
            if order is not None:
                signal.orderId = order.id
                db.update_signal_order(signal.id, order.id)
                print(f"Order placed for {symbol} with id {order.id}.")

        elif signal.action == "Sell":
            # if signal.orderId is None:
            #     print(f"No order found for {symbol}.")
            #     continue

            # order = client.get_order_by_id(signal.orderId)
            # if order is None:
            #     print(f"Order {signal.orderId} not found.")
            #     continue

            print(f"Selling {symbol} at {signal.metadata['close']}.")
            order = client.close_position(symbol)
            if order is not None:
                signal.orderId = order.id
                db.update_signal_order(signal.id, order.id)
                print(f"Order placed for {symbol} with id {order.id}.")


@cli.command()
def monitor_orders():
    """Monitor open orders and execute stop losses."""

    async def _trade_event_handler(event: str, order: dict):
        ao_key = f"alpaca_{order['id']}"
        db.upsert_order(ao_key, order)
        print(
            f"{event}: {order['side']} {order['order_type']} order {order['symbol']}."
        )

    cfg = TradeConfig()
    db = TraderDatabase(cfg)
    client = AlpacaClient(cfg.alpaca_key, cfg.alpaca_secret, cfg.alpaca_paper)
    enabled, account = client.account()
    if not enabled:
        print("Account is not enabled for trading. Exiting.")
        return

    def signal_handler(sig, frame):
        print(f"Received shutdown event: {system_signal.Signals(sig).name}.")
        client.close_stream()
        print("Gracefully shutdown. Exiting")
        sys.exit(0)

    system_signal.signal(system_signal.SIGINT, signal_handler)
    system_signal.signal(system_signal.SIGTERM, signal_handler)

    print("Starting order stream.")
    client.get_order_stream(_trade_event_handler)


def _convert_signal_to_action(signal):
    signal_date = localtime.localize_to_et(signal.name).date()
    today = localtime.today().date()
    days_old = (today - signal_date).days

    if signal["RSI_Buy"] == True and days_old <= 1:  # noqa: E712
        return "Buy"
    elif signal["RSI_Sell"] == True:  # noqa: E712
        return "Sell"
    else:
        return "Hold"


def _df_row_to_signal(symbol, row):
    signal = {}
    signal["date"] = localtime.to_day(row.name)
    signal["symbol"] = symbol
    signal["action"] = _convert_signal_to_action(row)

    signal["metadata"] = {}
    signal["metadata"]["open"] = round(row["open"], 4)
    signal["metadata"]["close"] = round(row["close"], 4)
    signal["metadata"]["rsi"] = round(row["RSI"], 2)
    return signal


def _get_trade_key(symbol, signal):
    d = signal["date"]
    return f"{symbol}_{d.strftime('%Y-%m-%d')}_RSI_{signal['action']}".lower()


if __name__ == "__main__":
    cli()
