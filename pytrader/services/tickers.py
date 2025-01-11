import logging as l
from joblib import Memory
from pandas import read_html, Timestamp
from .yf_data import ny_tz

cachedir = "./.cache/tickers"
memory = Memory(cachedir, verbose=0)


@memory.cache
def get_tickers(refresh_date: str = Timestamp.now(tz=ny_tz).floor("D")):
    l.debug(refresh_date)
    sp500 = read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
    sp500["Symbol"] = sp500["Symbol"].str.replace(".", "-")
    symbols_list = sp500["Symbol"].unique().tolist()

    QQQ = read_html("https://en.wikipedia.org/wiki/Nasdaq-100#Components")[4]
    QQQ["Symbol"] = QQQ["Symbol"].str.replace(".", "-")
    nasdaq_symbols_list = QQQ["Symbol"].unique().tolist()

    symbols_list.extend(nasdaq_symbols_list)
    symbols_list.extend(
        [
            "SPY",
            "IVV",
            "VOO",
            "VTI",
            "QQQ",
            "VEA",
            "IEFA",
            "VTV",
            "BND",
            "VUG",
            "AGG",
            "IWF",
            "IJR",
            "IJH",
            "IEMG",
            "VWO",
            "VIG",
            "IWM",
            "VXUS",
            "VO",
            "VGT",
            "XLK",
            "GLD",
            "IWD",
            "BNDX",
            "XXXX",
            "GBTC",
            "SMH",
            "IBIT",
            "VGT",
            "XLK",
            "BITO",
        ]
    )
    symbols_list = list(set(symbols_list))

    return symbols_list
