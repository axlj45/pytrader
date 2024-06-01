import os

from services import get_adjusted_market_data, get_tickers
from filters import filter_by_dollar_vol
from algos import calculate_signals as calc_bullish_rsi
from joblib import Memory

memory = Memory(os.path.join(os.getcwd(), ".cache", "rsi"), verbose=0)


@memory.cache
def _cached_rsi_signals(cache_key=None):
    tickers = get_tickers()
    data = get_adjusted_market_data(tickers)
    filtered_data = filter_by_dollar_vol(data)
    signals = calc_bullish_rsi(filtered_data, data)
    return signals


def rsi_signals(refresh=False):
    if refresh:
        memory.clear()
    signals = _cached_rsi_signals()
    return signals
