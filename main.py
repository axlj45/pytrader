import datetime
import os

import click
from dotenv import load_dotenv
from joblib import Memory


from services import get_adjusted_market_data, get_tickers
from filters import filter_by_dollar_vol
from algos import calculate_signals as calc_bullish_rsi
from services.alpaca import AlpacaClient


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

    signals_by_ticker = cached_rsi_signals()

    for ticker in signals_by_ticker:
        signal_data = signals_by_ticker[ticker]
        # get the last signal from pandas series

        last_signal = _data_row_to_signal(ticker, signal_data.iloc[-1])
        d = last_signal["date"]
        today = datetime.datetime.today()
        market_days = None

        if last_signal["action"] == "Buy":
            market_days = client.get_open_market_days_since(d)
            next_trade_day = client.get_next_trade_day()

            print(
                f"Buy Signal for {ticker} on {d} is {(today.date() - d).days} days old but {len(market_days)} market days old."
            )
            print(
                f"Next trade day is {next_trade_day} which is {(next_trade_day - today.date()).days} days away."
            )
            print(last_signal)

        elif last_signal["action"] == "Sell":
            print(
                f"Sell Signal for {ticker} on {d} is {today - d} days old but {len(market_days)} market days old."
            )

        if last_signal["action"] is not None:
            key = f"{ticker}_{today}_RSI_{last_signal['action']}".lower()
            print(key)
            pass


def _convert_signal_to_action(signal):
    signal_date = signal.name.date()
    today = datetime.datetime.today().date()
    days_old = (today - signal_date).days

    if signal["RSI_Buy"] == True and days_old <= 3:
        return "Buy"
    elif signal["RSI_Sell"] == True:
        return "Sell"
    else:
        return "Hold"


def _data_row_to_signal(ticker, row):
    signal = {}
    signal["date"] = row.name.date()
    signal["ticker"] = ticker
    signal["action"] = _convert_signal_to_action(row)

    signal["metadata"] = {}
    signal["metadata"]["open"] = round(row["open"], 4)
    signal["metadata"]["close"] = round(row["close"], 4)
    signal["metadata"]["rsi"] = round(row["RSI"], 2)
    return signal


@cli.command()
@click.option("--live", is_flag=True, help="Execute against live account.")
def connect_alpaca(live: bool):
    """Test connectivity to Alpaca API and print account information."""
    print("Connecting to Alpaca API...")

    # orders that satisfy params
    orders = client.get_orders()
    print(orders)

    positions = client.get_positions()
    print(positions)


if __name__ == "__main__":
    cli()
