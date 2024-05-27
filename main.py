import os

import click
from dotenv import load_dotenv
from joblib import Memory


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
    # signals = calc_bullish_rsi(filtered_data, data)

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
            print(last_signal)
            market_days = client.get_open_market_days_since(d)
            next_trade_day = client.get_next_trade_day()

            # create trade and store in db
            trade = TradeModel.create_trade(symbol, key, "RSI", next_trade_day)
            trade.signals = [last_signal]

            result = db.add_trade(trade)

            if result is None:
                print(f"Trade with id {key} already exists.")
                continue

            print(result.to_dict())

            print(
                f"Buy Signal for {symbol} on {d} is {(today - d).days} days old but {len(market_days)} market days old."
            )
            print(
                f"Next trade day is {next_trade_day} which is {(next_trade_day - today).days} days away."
            )

        elif last_signal["action"] == "Sell":
            buy_signal = _df_row_to_signal(symbol, signal_data.iloc[-2])
            buy_key = _get_trade_key(symbol, buy_signal)
            open_trade = db.get_trade(buy_key)

            print(
                f"Sell Signal for {symbol} on {d} is {today - d} days old but {len(market_days)} market days old."
            )


@cli.command()
def process_signals():
    """Process RSI signals and execute trades."""
    db = TraderDatabase()
    trades = db.get_pending_trades()
    print([trade.to_dict() for trade in trades])


def _convert_signal_to_action(signal):
    signal_date = localtime.localize_to_et(signal.name).date()
    today = localtime.today().date()
    days_old = (today - signal_date).days

    if signal["RSI_Buy"] == True and days_old <= 3:  # noqa: E712
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
