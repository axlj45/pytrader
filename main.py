import os

import click
from dotenv import load_dotenv
from joblib import Memory


from model.signal import SignalModel
from model.trade import TradeModel
from services import get_adjusted_market_data, get_tickers
from filters import filter_by_dollar_vol
from algos import calculate_signals as calc_bullish_rsi
from services.alpaca import AlpacaClient
from services.database import TraderDatabase
from utils import localtime


load_dotenv()
memory = Memory(os.path.join(os.getcwd(), ".cache", "rsi"), verbose=0)
client = AlpacaClient(
    os.getenv("alpaca_api_key"), os.getenv("alpaca_secret_key"), paper=True
)


@click.group()
def cli():
    pass


@memory.cache
def cached_rsi_signals():
    """Temporary to speed up debugging."""
    tickers = get_tickers()
    data = get_adjusted_market_data(tickers)
    filtered_data = filter_by_dollar_vol(data)
    signals = calc_bullish_rsi(filtered_data, data)
    return signals


@cli.command()
@click.option("--live", is_flag=True, help="Execute against live account.")
def rsi(live: bool):
    """Calculate RSI signals for all tickers in the S&P 500."""
    # tickers = get_tickers()
    # data = get_adjusted_market_data(tickers)
    # filtered_data = filter_by_dollar_vol(data)
    # signals_by_symbol = calc_bullish_rsi(filtered_data, data)

    signals_by_symbol = cached_rsi_signals()
    db = TraderDatabase()

    for symbol in signals_by_symbol:
        signal_data = signals_by_symbol[symbol]
        # get the last signal from pandas series

        last_signal = _df_row_to_signal(symbol, signal_data.iloc[-1])

        d = last_signal["date"]
        today = localtime.today()
        market_days = None
        key = _get_trade_key(symbol, last_signal)

        if last_signal["action"] == "Buy":
            market_days = client.get_open_market_days_since(d)
            next_trade_day = client.get_next_trade_day()

            # create trade and store in db
            signal = SignalModel.create_signal(
                symbol, key, "Buy", "RSI", last_signal["metadata"], next_trade_day
            )
            trade = TradeModel.create_trade(symbol, key, "RSI", [])

            result = db.add_signal(signal)

            if result is None:
                print(f"{key} already exists.")
                continue

            db.add_trade(trade)
            db.add_signal_ref_to_trade(trade.id, signal.id)

            print(
                f"Buy Signal for {symbol} on {d} is {(today - d).days} days old but {len(market_days)} market days old."
            )
            print(
                f"Next trade day is {next_trade_day} which is {(next_trade_day - today).days} days away."
            )

        elif last_signal["action"] == "Sell":
            buy_signal = _df_row_to_signal(symbol, signal_data.iloc[-2])
            buy_key = _get_trade_key(symbol, buy_signal)
            trade = db.get_trade(buy_key)

            if trade is None:
                print(f"Trade not found for {buy_key}.")
                continue

            market_days = client.get_open_market_days_since(d)
            next_trade_day = client.get_next_trade_day()

            sell_signal = SignalModel.create_signal(
                symbol, key, "Sell", "RSI", last_signal["metadata"], next_trade_day
            )
            db.add_signal(sell_signal)

            if result is None:
                print(f"{key} already exists.")
                continue

            trade.signals.append(sell_signal.id)
            db.add_signal_ref_to_trade(trade.id, sell_signal.id)

            print(
                f"Sell Signal for {symbol} on {d} is {today - d} days old but {len(market_days)} market days old."
            )


@cli.command()
def process_signals():
    """Process RSI signals and execute trades."""

    enabled, account = client.account()
    if not enabled:
        print("Account is not enabled for trading. Exiting.")
        return
    db = TraderDatabase()

    account_value = float(account.portfolio_value)
    cash = float(account.non_marginable_buying_power)
    max_trade_value = account_value * 0.05

    print(f"Account Value: {account_value}")
    print(f"Cash: {cash}")

    signals = db.get_pending_signals()

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


def _convert_signal_to_action(signal):
    signal_date = localtime.localize_to_et(signal.name).date()
    today = localtime.today().date()
    days_old = (today - signal_date).days

    if signal["RSI_Buy"] == True and days_old <= 4:  # noqa: E712
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
