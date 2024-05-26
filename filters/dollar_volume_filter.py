from pandas import DataFrame


def filter_by_dollar_vol(
    df: DataFrame,
    take_top: int = 100,
    price_col: str = "close",
    vol_col: str = "volume",
) -> DataFrame:
    df["dollar_volume"] = (df[price_col] * df[vol_col]) / 1e6

    data = df.copy()

    data["dollar_volume"] = (
        data.loc[:, "dollar_volume"]
        .unstack("ticker")
        .rolling(1 * 30, min_periods=12)
        .mean()
        .stack()
    )

    data["dollar_vol_rank"] = data.groupby("date")["dollar_volume"].rank(
        ascending=False
    )

    data = data[data["dollar_vol_rank"] < take_top].drop(
        ["dollar_volume", "dollar_vol_rank"], axis=1
    )

    return data
