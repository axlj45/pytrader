import pytest
import pandas as pd
from datetime import datetime
from unittest import mock
from pytrader.algos.bullish_rsi_signal import calculate_signals


@pytest.fixture
def sample_data():
    data = {
        "symbol": ["AAPL"] * 10,
        "date": pd.date_range(start="2023-01-01", periods=10, freq="D"),
        "open": [150, 152, 153, 155, 157, 158, 160, 162, 161, 159],
        "close": [152, 153, 155, 157, 158, 160, 162, 161, 159, 158],
        "high": [153, 154, 156, 158, 159, 161, 163, 162, 160, 159],
        "low": [149, 151, 152, 154, 156, 157, 159, 160, 158, 157],
        "volume": [1000000, 1100000, 1050000, 1150000, 1200000, 1250000, 1300000, 1350000, 1400000, 1450000],
        "dollar_volume": [
            150000000,
            152000000,
            153000000,
            155000000,
            157000000,
            158000000,
            160000000,
            162000000,
            161000000,
            159000000,
        ],
    }
    df = pd.DataFrame(data)
    df.set_index(["date", "symbol"], inplace=True)
    return df


@pytest.fixture
def all_tickers_df(sample_data):
    return sample_data


def test_calculate_signals(sample_data, all_tickers_df):
    with mock.patch("datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = datetime(2023, 1, 10)
        result = calculate_signals(sample_data, all_tickers_df)
        assert result is not None
