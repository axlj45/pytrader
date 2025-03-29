import yfinance as yf
import pandas as pd
from pytz import timezone

from requests import Session
from requests_cache import CacheMixin, SQLiteCache
from requests_ratelimiter import LimiterMixin, MemoryQueueBucket
from pyrate_limiter import Duration, RequestRate, Limiter

ny_tz = timezone("America/New_York")
yf.set_tz_cache_location("./.cache/yf_tz_cache")


class CachedLimiterSession(CacheMixin, LimiterMixin, Session):
    pass


def get_adjusted_market_data(
    tickers: list[str],
    interval: str = "1d",
    end_date: pd.Timestamp = pd.Timestamp.now(tz=ny_tz).floor("60min"),
    start_date: pd.Timestamp = None,
) -> pd.DataFrame:
    if start_date is None:
        start_date = (pd.to_datetime(end_date) - pd.DateOffset(1600)).floor("60min")

    session = CachedLimiterSession(
        limiter=Limiter(RequestRate(2, Duration.SECOND)),
        bucket_class=MemoryQueueBucket,
        backend=SQLiteCache("yfinance.cache"),
    )

    df = yf.download(
        tickers=tickers,
        start=start_date,
        end=end_date,
        interval=interval,
        auto_adjust=True,
        threads=3,
        session=session,
    )
    
    # Remove tickers that failed to download (all data is NaN)
    df = df.dropna(axis=1, how="all")

    df = df.stack(future_stack=True)
    df.index.names = ["date", "ticker"]
    df.columns = df.columns.str.lower()

    return df
