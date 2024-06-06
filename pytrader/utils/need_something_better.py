from pytrader.utils import localtime


def _convert_signal_to_action(signal: dict):
    signal_date = localtime.localize_to_et(signal.name).date()
    today = localtime.today().date()
    days_old = (today - signal_date).days

    if signal["RSI_Buy"] == True and days_old <= 1:  # noqa: E712
        return "Buy"
    elif signal["RSI_Sell"] == True:  # noqa: E712
        return "Sell"
    else:
        return "Hold"


def _df_row_to_signal(symbol: str, row):
    signal = {}
    signal["date"] = localtime.to_day(row.name)
    signal["symbol"] = symbol
    signal["action"] = _convert_signal_to_action(row)

    signal["metadata"] = {}
    signal["metadata"]["open"] = round(row["open"], 4)
    signal["metadata"]["close"] = round(row["close"], 4)
    signal["metadata"]["rsi"] = round(row["RSI"], 2)
    return signal


def _get_trade_key(symbol: str, signal: dict):
    d = signal["date"]
    return f"{symbol}_{d.strftime('%Y-%m-%d')}_RSI_{signal['action']}".lower()
