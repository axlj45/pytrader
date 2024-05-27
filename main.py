import click
import pandas as pd
from dotenv import load_dotenv
import os

from services import get_adjusted_market_data, get_tickers
from filters import filter_by_dollar_vol
from algos import calculate_signals as calc_bullish_rsi

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import OrderSide, QueryOrderStatus

load_dotenv()


@click.group()
def cli():
    pass


@cli.command()
def rsi():
    tickers = get_tickers()
    data = get_adjusted_market_data(tickers)
    filtered_data = filter_by_dollar_vol(data)
    buys = calc_bullish_rsi(filtered_data, data)

    with pd.option_context("display.float_format", "{:0.2f}".format):
        for buy in buys:
            print(buy)
            print(buys[buy])


@cli.command()
def connect_alpaca():
    print("Connecting to Alpaca API...")
    client = TradingClient(
        os.getenv("alpaca_api_key"), os.getenv("alpaca_secret_key"), paper=True
    )

    # orders that satisfy params
    orders = client.get_orders()
    print(orders)

    positions = client.get_all_positions()
    print(positions)


if __name__ == "__main__":
    cli()
