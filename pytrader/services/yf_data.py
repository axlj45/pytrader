from joblib import Memory
import yfinance as yf
import pandas as pd
from pytz import timezone
import warnings

warnings.simplefilter(action="ignore", category=FutureWarning)
ny_tz = timezone("America/New_York")
cachedir = "./.cache/yfinance"
memory = Memory(cachedir, verbose=0)


@memory.cache
def _cached_yf_download(*args, **kwargs):
    return yf.download(*args, **kwargs)


def get_adjusted_market_data(
    tickers: list[str],
    interval: str = "1d",
    end_date: pd.Timestamp = pd.Timestamp.now(tz=ny_tz).floor("60T"),
    start_date: pd.Timestamp = None,
) -> pd.DataFrame:
    if start_date is None:
        start_date = (pd.to_datetime(end_date) - pd.DateOffset(1600)).floor("60T")

    df = _cached_yf_download(
        tickers=tickers,
        start=start_date,
        end=end_date,
        interval=interval,
        auto_adjust=True,
        threads=1
    )
    
    df = df.stack()
    df.index.names = ["date", "ticker"]
    df.columns = df.columns.str.lower()

    return df
