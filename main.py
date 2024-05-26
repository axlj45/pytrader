import click
import pandas as pd

from services import get_adjusted_market_data, get_tickers
from filters import filter_by_dollar_vol
from algos import calculate_signals as calc_bullish_rsi


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


if __name__ == "__main__":
    cli()
