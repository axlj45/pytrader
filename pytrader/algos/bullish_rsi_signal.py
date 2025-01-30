import logging as l
import datetime
import pandas as pd


def _rsi_buy(df):
    return (df["close"] > df["200sma"]) and df["RSI"] < 30


_in_buy_phase = False


def _filter_signals(row):
    global _in_buy_phase
    if row["RSI_Buy"] == True and not _in_buy_phase:
        _in_buy_phase = True
        return True
    if row["RSI_Sell"] == True and _in_buy_phase:
        _in_buy_phase = False
        return True
    return False


def rsi_sell(window):
    open_position = 0
    current_value = window.iloc[len(window) - 1]
    blew_rsi = False

    for i in range(len(window)):
        old_value = window.iloc[len(window) - i - 1]
        if old_value["RSI_Buy"] == False:
            continue
        open_position = i
        if current_value["RSI"] > 40:
            blew_rsi = True

    if open_position >= 10 or blew_rsi:
        return True

    return False


def calculate_signals(symbol_data: pd.DataFrame, all_tickers_df: pd.DataFrame):
    buys = {}

    for symbol in symbol_data.index.unique(1):
        try:
            df = all_tickers_df.xs(symbol, level=1).drop_duplicates()

            df["200sma"] = df["close"].rolling(window=200).mean()

            df["price_change"] = df["close"].pct_change()
            df["Upmove"] = df["price_change"].apply(lambda x: x if x > 0 else 0)
            df["Downmove"] = df["price_change"].apply(lambda x: abs(x) if x < 0 else 0)
            df["avg_up"] = df["Upmove"].ewm(span=19).mean()
            df["avg_down"] = df["Downmove"].ewm(span=19).mean()
            df = df.dropna()
            df["RS"] = df["avg_up"] / df["avg_down"]
            df["RSI"] = df["RS"].apply(lambda x: 100 - (100 / (x + 1)))

            df["RSI_Buy"] = df.apply(_rsi_buy, axis=1)
            df["Periods_Since_Buy"] = df.loc[df["RSI_Buy"]].index.to_series().diff().fillna(0)

            results = []
            for i in range(len(df)):
                if i < 10:
                    results.append(False)
                    continue
                window_df = df[max(i - 10 + 1, 0) : i + 1]
                result = rsi_sell(window_df)
                results.append(result)

            df["RSI_Sell"] = results
            df["tx_price"] = df["open"].shift(-1)

            df["keep"] = df.apply(_filter_signals, axis=1)
            # print(df[df['keep']].count(numeric_only=True))
            filtered_df = df[df["keep"]].drop(columns="keep")

            filtered_df.drop(
                [
                    "high",
                    "low",
                    "price_change",
                    "volume",
                    "dollar_volume",
                    "avg_up",
                    "avg_down",
                    "Upmove",
                    "Downmove",
                    "200sma",
                    "RS",
                ],
                inplace=True,
                axis=1,
            )

            filtered_df[filtered_df["RSI_Buy"] | filtered_df["RSI_Sell"]]

            latest_buy = filtered_df[filtered_df["RSI_Buy"]].tail(1)
            if len(latest_buy) == 1:
                d = latest_buy.iloc[0].name.date()
                # print(f"{symbol}: {d}")
                now = datetime.datetime.now().date()
                isWithinDays = (now - d).days <= 10
                if isWithinDays:
                    l.info(f"{symbol}: {(d - now).days}: {d}")
                    buys[symbol] = filtered_df
        except Exception as ex:
            l.warning(f"{symbol}: {ex}")

    return buys
