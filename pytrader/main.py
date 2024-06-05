import logging
import signal as system_signal
import sys

import click

from model import SignalModel, TradeModel
from services import AlpacaClient, TraderDatabase, rsi_signals
from utils import localtime, TradeConfig


@click.group()
@click.pass_context
@click.option("-c", "--config", default=None, help="Path to configuration file.")
@click.option("-l", "--live", is_flag=True, help="Execute against live account.")
@click.option("--log-path", default="pytrader.log", help="Path to write log file.")
@click.option(
    "-v",
    "--log-level",
    type=click.Choice(
        [
            "DEBUG",
            "INFO",
            "WARNING",
            "ERROR",
            "CRITICAL",
            "FATAL",
        ],
        case_sensitive=False,
    ),
    default="INFO",
    show_default=True,
    help="Set log level",
)
def cli(ctx: click.Context, config: str, live: bool, log_path: str, log_level: str):
    numeric_level = getattr(logging, log_level.upper(), None)

    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.FileHandler(log_path), logging.StreamHandler()],
    )

    ctx.ensure_object(dict)
    cfg = TradeConfig(config)
    ctx.obj["db"] = TraderDatabase(cfg)
    ctx.obj["client"] = AlpacaClient(
        cfg.alpaca_key, cfg.alpaca_secret, live or cfg.alpaca_paper
    )
    pass


@cli.command()
@click.pass_context
@click.option("--refresh", is_flag=True, help="Force refresh of RSI signals.")
def rsi(ctx: click.Context, refresh: bool):
    """Calculate RSI signals for all tickers in the S&P 500."""
    signals_by_symbol = rsi_signals(refresh)
    client: AlpacaClient = ctx.obj["client"]
    db: TraderDatabase = ctx.obj["db"]
    l = logging.getLogger("pytrader.signals.rsi")
    for symbol in signals_by_symbol:
        signal_data = signals_by_symbol[symbol]
        last_signal = _df_row_to_signal(symbol, signal_data.iloc[-1])

        d = last_signal["date"]
        today = localtime.today()
        market_days = None
        key = _get_trade_key(symbol, last_signal)

        if last_signal["action"] == "Buy":
            market_days = client.get_open_market_days_since(d)
            next_trade_day = client.get_next_trade_day()

            signal = SignalModel.create_signal(
                symbol, key, "Buy", "RSI", last_signal["metadata"], next_trade_day
            )
            result = db.add_signal(signal)

            if result is None:
                l.warn(f"BUY signal for {symbol} has already been triggered: {key}.")
                continue

            trade = TradeModel.create_trade(symbol, key, "RSI", [])
            db.add_trade(trade)
            db.add_signal_ref_to_trade(trade.id, signal.id)

            l.debug(
                f"Buy Signal for {symbol} on {d} is {(today - d).days} days old but {len(market_days)} market days old."
            )
            l.debug(
                f"Next trade day is {next_trade_day} which is {(next_trade_day - today).days} days away."
            )

        elif last_signal["action"] == "Sell":
            market_days = client.get_open_market_days_since(d)
            buy_signal = _df_row_to_signal(symbol, signal_data.iloc[-2])
            buy_key = _get_trade_key(symbol, buy_signal).replace("hold", "buy")

            trade = db.get_trade(buy_key)

            if trade is None:
                l.warn(
                    f"Close signal triggered for {symbol} but no opening trade could be located: {buy_key}."
                )
                continue

            open_signal = (
                trade.resolved_signals[0]
                if len(trade.resolved_signals or []) > 0
                else None
            )

            if open_signal is None:
                msg = f"Close signal triggered for {symbol} but no opening signal could be found for {buy_key}."
                l.warning(msg)
                continue

            open_order = client.get_order_by_id(open_signal.orderId)
            if open_order is None or open_order.status not in [
                "filled",
                "partially_filled",
            ]:
                msg = f"Close signal triggered for {symbol} but no filled orders could be found for {buy_key}."
                l.warn(msg)
                continue

            next_trade_day = client.get_next_trade_day()

            close_signal = SignalModel.create_signal(
                symbol, key, "Sell", "RSI", last_signal["metadata"], next_trade_day
            )
            result = db.add_signal(close_signal)

            if result is None:
                l.warning(
                    f"Close signal for {symbol} has already been triggered: {key}."
                )
                continue

            db.add_signal_ref_to_trade(trade.id, close_signal.id)

            l.info(f"Close Signal for {symbol}")


@cli.command()
@click.pass_context
def process_signals(ctx: click.Context):
    """Process RSI signals and execute trades."""
    client: AlpacaClient = ctx.obj["client"]
    db: TraderDatabase = ctx.obj["db"]
    l = logging.getLogger("pytrader.signal.processor")
    enabled, account = client.account()
    if not enabled:
        l.error("Account is not enabled for trading. Exiting.")
        return

    account_value = float(account.portfolio_value)
    cash = float(account.non_marginable_buying_power)
    max_trade_value = account_value * 0.05
    l.info("Beginning signal processing")
    l.debug(f"Account Value: {account_value}")
    l.debug(f"Cash: {cash}")

    signals = db.get_pending_signals()
    l.info(f"Processing {len(signals)} signals.")

    for signal in signals:
        symbol = signal.symbol

        if signal.action == "Buy":
            if cash < max_trade_value:
                l.warning(f"Insufficient cash to buy {symbol}.")
                continue

            last_close_price = signal.metadata["close"]
            last_open_price = signal.metadata["open"]
            stop_price = last_close_price * 0.98

            existing_cost_basis = 0

            position = client.get_position_for(symbol)
            if position is not None:
                existing_cost_basis = float(position.avg_entry_price) * int(
                    position.qty
                )

            l.debug(f"Existing cost basis for {symbol}: {existing_cost_basis}")
            available_symbol_funds = max_trade_value - existing_cost_basis

            qty = int(available_symbol_funds / last_close_price)
            if qty == 0:
                l.warning(f"Insufficient funds to buy {symbol}.")
                continue

            l.info(f"Buying {qty} shares of {symbol} at {last_open_price}.")

            order = client.buy_with_stop_loss(symbol, qty, last_open_price, stop_price)
            if order is not None:
                signal.orderId = order.id
                db.update_signal_order(signal.id, order.id)
                l.info(f"Order placed for {symbol} with id {order.id}.")

        elif signal.action == "Sell":
            order = client.close_position(symbol)
            if order is not None:
                signal.orderId = order.id
                db.update_signal_order(signal.id, order.id)
                l.info(f"Sell order placed for {symbol} with id {order.id}.")
            else:
                l.warning(f"Failed to place order for {symbol}. id: {signal.id}.")


@cli.command()
@click.pass_context
def monitor_orders(ctx: click.Context):
    """Monitor open orders and execute stop losses."""
    db: TraderDatabase = ctx.obj["db"]
    client: AlpacaClient = ctx.obj["client"]
    l = logging.getLogger("pytrader.broker.order_monitor")

    async def _trade_event_handler(event: str, order: dict):
        ao_key = f"alpaca_{order['id']}"
        db.upsert_order(ao_key, order)
        l.info(
            f"{event}: {order['side']} {order['order_type']} order {order['symbol']}."
        )

    enabled, account = client.account()
    if not enabled:
        l.error("Account is not enabled for trading. Exiting.")
        return -1

    def signal_handler(sig, frame):
        l.info(f"Received shutdown event: {system_signal.Signals(sig).name}.")
        client.close_stream()
        l.info("Gracefully shutdown. Exiting")
        sys.exit(0)

    system_signal.signal(system_signal.SIGINT, signal_handler)
    system_signal.signal(system_signal.SIGTERM, signal_handler)

    l.info("Starting order stream.")
    client.get_order_stream(_trade_event_handler)


def _convert_signal_to_action(signal):
    signal_date = localtime.localize_to_et(signal.name).date()
    today = localtime.today().date()
    days_old = (today - signal_date).days

    if signal["RSI_Buy"] == True and days_old <= 1:  # noqa: E712
        return "Buy"
    elif signal["RSI_Sell"] == True:  # noqa: E712
        return "Sell"
    else:
        return "Hold"


def _df_row_to_signal(symbol, row):
    signal = {}
    signal["date"] = localtime.to_day(row.name)
    signal["symbol"] = symbol
    signal["action"] = _convert_signal_to_action(row)

    signal["metadata"] = {}
    signal["metadata"]["open"] = round(row["open"], 4)
    signal["metadata"]["close"] = round(row["close"], 4)
    signal["metadata"]["rsi"] = round(row["RSI"], 2)
    return signal


def _get_trade_key(symbol, signal):
    d = signal["date"]
    return f"{symbol}_{d.strftime('%Y-%m-%d')}_RSI_{signal['action']}".lower()


if __name__ == "__main__":
    cli(obj={})
