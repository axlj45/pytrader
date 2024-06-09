import logging
import signal as system_signal
import sys

import click

from pytrader.model import SignalModel, TradeModel
from pytrader.services import AlpacaClient, TraderDatabase, rsi_signals
from pytrader.utils import localtime, TradeConfig
from pytrader.utils.need_something_better import _df_row_to_signal, _get_trade_key


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
    log = logging.getLogger("pytrader.signals.rsi")

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
                log.warning(
                    f"BUY signal for {symbol} has already been triggered: {key}."
                )
                continue

            trade = TradeModel.create_trade(symbol, key, "RSI", [])
            db.add_trade(trade)
            db.add_signal_ref_to_trade(trade.id, signal.id)

            log.debug(
                f"Buy Signal for {symbol} on {d} is {(today - d).days} days old but {len(market_days)} market days old."
            )
            log.debug(
                f"Next trade day is {next_trade_day} which is {(next_trade_day - today).days} days away."
            )

        elif last_signal["action"] == "Sell":
            market_days = client.get_open_market_days_since(d)
            buy_signal = _df_row_to_signal(symbol, signal_data.iloc[-2])
            buy_key = _get_trade_key(symbol, buy_signal).replace("hold", "buy")

            trade = db.get_trade(buy_key)

            if trade is None:
                log.warning(
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
                log.warning(msg)
                continue

            open_order = client.get_order_by_id(open_signal.orderId)
            if open_order is None or open_order.status not in [
                "filled",
                "partially_filled",
            ]:
                msg = f"Close signal triggered for {symbol} but no filled orders could be found for {buy_key}."
                log.warning(msg)
                continue

            next_trade_day = client.get_next_trade_day()

            close_signal = SignalModel.create_signal(
                symbol, key, "Sell", "RSI", last_signal["metadata"], next_trade_day
            )
            result = db.add_signal(close_signal)

            if result is None:
                log.warning(
                    f"Close signal for {symbol} has already been triggered: {key}."
                )
                continue

            db.add_signal_ref_to_trade(trade.id, close_signal.id)

            log.info(f"Close Signal for {symbol}")


@cli.command()
@click.pass_context
def process_signals(ctx: click.Context):
    """Process RSI signals and execute trades."""
    client: AlpacaClient = ctx.obj["client"]
    db: TraderDatabase = ctx.obj["db"]
    log = logging.getLogger("pytrader.signal.processor")
    enabled, account = client.account()
    if not enabled:
        log.error("Account is not enabled for trading. Exiting.")
        return

    account_value = float(account.portfolio_value)
    cash = float(account.non_marginable_buying_power)
    max_trade_value = account_value * 0.05
    log.info("Beginning signal processing")
    log.debug(f"Account Value: {account_value}")
    log.debug(f"Cash: {cash}")

    signals = db.get_pending_signals()
    log.info(f"Processing {len(signals)} signals.")

    for signal in signals:
        symbol = signal.symbol

        if signal.action == "Buy":
            if cash < max_trade_value:
                log.warning(f"Insufficient cash to buy {symbol}.")
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

            log.debug(f"Existing cost basis for {symbol}: {existing_cost_basis}")
            available_symbol_funds = max_trade_value - existing_cost_basis

            qty = int(available_symbol_funds / last_close_price)
            if qty == 0:
                log.warning(f"Insufficient funds to buy {symbol}.")
                continue

            log.info(f"Buying {qty} shares of {symbol} at {last_open_price}.")

            order = client.buy_with_stop_loss(symbol, qty, last_open_price, stop_price)
            if order is not None:
                signal.orderId = order.id
                db.update_signal_order(signal.id, order.id)
                log.info(f"Order placed for {symbol} with id {order.id}.")

        elif signal.action == "Sell":
            order = client.close_position(symbol)
            if order is not None:
                signal.orderId = order.id
                db.update_signal_order(signal.id, order.id)
                log.info(f"Sell order placed for {symbol} with id {order.id}.")
            else:
                log.warning(f"Failed to place order for {symbol}. id: {signal.id}.")


@cli.command()
@click.pass_context
def monitor_orders(ctx: click.Context):
    """Monitor open orders and execute stop losses."""
    db: TraderDatabase = ctx.obj["db"]
    client: AlpacaClient = ctx.obj["client"]
    log = logging.getLogger("pytrader.broker.order_monitor")

    async def _trade_event_handler(event: str, order: dict):
        ao_key = f"alpaca_{order['id']}"
        db.upsert_order(ao_key, order)
        log.info(
            f"{event}: {order['side']} {order['order_type']} order {order['symbol']}."
        )

    enabled, account = client.account()
    if not enabled:
        log.error("Account is not enabled for trading. Exiting.")
        return -1

    def signal_handler(sig, frame):
        log.info(f"Received shutdown event: {system_signal.Signals(sig).name}.")
        client.close_stream()
        log.info("Gracefully shutdown. Exiting")
        sys.exit(0)

    system_signal.signal(system_signal.SIGINT, signal_handler)
    system_signal.signal(system_signal.SIGTERM, signal_handler)

    log.info("Starting order stream.")
    client.get_order_stream(_trade_event_handler)


@cli.command()
@click.pass_context
def complete_the_trade(ctx: click.Context):
    db: TraderDatabase = ctx.obj["db"]
    broker = ctx.obj["client"]
    trades = db.get_trades()
    for tradeDoc in trades:
        trade = db.get_trade(tradeDoc.id)

        trade_incomplete = len(trade.resolved_signals) < 2
        if trade_incomplete:
            print(f"Ignoring trade {trade.id}. it only has 1 signal")
            continue

        for signal in trade.resolved_signals:
            if (
                signal.resolvedOrder is None
                or signal.resolvedOrder["status"] != "FILLED"
            ):
                broker_order = broker.get_order_by_id(signal.orderId)
                if broker_order is not None:
                    signal.resolvedOrder = broker_order
                    ao_key = f"alpaca_{signal.orderId}"
                    db.upsert_order(ao_key, broker_order)
                else:
                    trade_incomplete = True
                    break

        if trade_incomplete:
            print(f"Ignoring trade {trade.id} as it is incomplete.")
            continue

        open_order = trade.resolved_signals[0].resolvedOrder
        close_order = trade.resolved_signals[-1].resolvedOrder

        open_qty = float(open_order["qty"])
        close_qty = float(close_order["qty"])

        if open_qty - close_qty != 0:
            print(f"Ignoring trade {trade.id}, quantities don't match. Open qty: {open_qty} Close qty: {close_qty}")
            continue

        cost_basis = float(open_order["filled_avg_price"])
        sale_price = float(close_order["filled_avg_price"])
        pct_change = round((sale_price - cost_basis) / cost_basis, 4) * 100
        market_exposure = (close_order["filled_at"] - open_order["filled_at"]).days

        revenue = round((sale_price - cost_basis) * open_qty, 2)
        print(trade.id, market_exposure, revenue, f"{pct_change}%")

    # Get all trades
    # Find trades with state = not closed
    # Add open order fill date
    # Add close order fill date
    # Add trade duration in days field
    # add cost basis
    # add market value at sale
    # add potential tax implications

    pass


if __name__ == "__main__":
    cli(obj={})
