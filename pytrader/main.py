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
@click.option("-o", "--log-path", default="pytrader.log", help="Path to write log file.")
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
    ctx.obj["broker"] = AlpacaClient(cfg.alpaca_key, cfg.alpaca_secret, live or cfg.alpaca_paper)
    ctx.obj["cfg"] = cfg


@cli.command()
@click.pass_context
@click.option("--refresh", is_flag=True, help="Force refresh of RSI signals.")
def rsi(ctx: click.Context, refresh: bool):
    """Calculate RSI signals for all tickers in the S&P 500."""
    signals_by_symbol = rsi_signals(refresh)
    broker: AlpacaClient = ctx.obj["broker"]
    db: TraderDatabase = ctx.obj["db"]
    cfg: TradeConfig = ctx.obj["cfg"]
    log = logging.getLogger("pytrader.signals.rsi")

    for symbol in signals_by_symbol:
        signal_data = signals_by_symbol[symbol]
        last_signal = _df_row_to_signal(symbol, signal_data.iloc[-1])

        d = last_signal["date"]
        today = localtime.today()
        market_days = None
        key = _get_trade_key(symbol, last_signal)

        if last_signal["action"] == "Buy":
            market_days = broker.get_open_market_days_since(d)
            next_trade_day = broker.get_next_trade_day()

            signal = SignalModel.create_signal(symbol, key, "Buy", "RSI", last_signal["metadata"], next_trade_day)
            result = db.add_signal(signal)

            if result is None:
                log.warning(f"BUY signal for {symbol} has already been triggered: {key}.")
                continue

            trade = TradeModel.create_trade(symbol, key, "RSI", [])
            db.add_trade(trade)
            db.add_signal_ref_to_trade(trade.id, signal.id)

            log.debug(
                f"Buy Signal for {symbol} on {d} is {(today - d).days} days old but {len(market_days)} market days old."
            )
            log.debug(f"Next trade day is {next_trade_day} which is {(next_trade_day - today).days} days away.")

        elif last_signal["action"] == "Sell":
            market_days = broker.get_open_market_days_since(d)
            buy_signal = _df_row_to_signal(symbol, signal_data.iloc[-2])
            buy_key = _get_trade_key(symbol, buy_signal).replace("hold", "buy")

            trade = db.get_trade(buy_key)

            if trade is None:
                log.warning(f"Close signal triggered for {symbol} but no opening trade could be located: {buy_key}.")
                continue

            open_signal = trade.resolved_signals[0] if len(trade.resolved_signals or []) > 0 else None

            if open_signal is None:
                msg = f"Close signal triggered for {symbol} but no opening signal could be found for {buy_key}."
                log.warning(msg)
                continue

            open_order = broker.get_order_by_id(open_signal.orderId)
            order_status = (open_order.get("status") or "").lower()
            if open_order is None or order_status not in [
                "filled",
                "partially_filled",
            ]:
                msg = f"Close signal triggered for {symbol} but no filled orders could be found for {buy_key}."
                log.warning(msg)
                continue

            next_trade_day = broker.get_next_trade_day()
            metadata = last_signal["metadata"]
            close_signal = SignalModel.create_signal(symbol, key, "Sell", "RSI", metadata, next_trade_day)
            result = db.add_signal(close_signal)

            if result is None:
                log.warning(f"Close signal for {symbol} has already been triggered: {key}.")
                continue

            db.add_signal_ref_to_trade(trade.id, close_signal.id)

            log.info(f"Close Signal for {symbol}")

    open_trades = db.get_trades()

    for tradeDoc in open_trades:
        trade = db.get_trade(tradeDoc.id)

        if len(trade.signals) != 1:
            continue

        today = localtime.today()
        executeDate = trade.resolved_signals[0].executeOn
        age = today - executeDate
        if age.days > cfg.rsi_timeout_days:
            log.warning(f"Trade timed out, creating closing signal for: {trade.id}")
            next_trade_day = broker.get_next_trade_day()
            key = _get_trade_key(trade.symbol, {"action": "SELL", "date": localtime.today()})
            signal = SignalModel.create_signal(trade.symbol, key, "Sell", "RSI", {"note": "Timed out"}, next_trade_day)
            result = db.add_signal(signal)
            if result is None:
                log.warning(f"Close signal for {trade.symbol} has already been triggered: {key}.")
                continue
            db.add_signal_ref_to_trade(trade.id, signal.id)
            log.info(f"Close Signal for {trade.symbol}")


@cli.command()
@click.pass_context
def process_signals(ctx: click.Context):
    """Process RSI signals and execute trades."""
    broker: AlpacaClient = ctx.obj["broker"]
    db: TraderDatabase = ctx.obj["db"]
    cfg: TradeConfig = ctx.obj["cfg"]
    log = logging.getLogger("pytrader.signal.processor")
    enabled, account = broker.account()
    if not enabled:
        log.error("Account is not enabled for trading. Exiting.")
        return

    account_value = float(account.portfolio_value)
    cash = float(account.non_marginable_buying_power)
    max_trade_value = account_value * cfg.max_single_symbol
    available_funds = cash * cfg.max_portfolio_usage
    available_trade_funds = min(available_funds, max_trade_value)
    log.info("Beginning signal processing")
    log.debug(f"Account Value: {account_value}")
    log.debug(f"Cash: {cash}")

    signals = db.get_pending_signals()
    log.info(f"Processing {len(signals)} signals.")

    for signal in signals:
        symbol = signal.symbol

        if signal.action == "Buy":
            last_close_price = signal.metadata["close"]
            last_open_price = signal.metadata["open"]
            stop_price = last_close_price * 0.98

            existing_cost_basis = 0

            position = broker.get_position_for(symbol)
            if position is not None:
                existing_cost_basis = float(position.avg_entry_price) * int(position.qty)

            log.debug(f"Existing cost basis for {symbol}: {existing_cost_basis}")
            available_symbol_funds = available_trade_funds - existing_cost_basis

            qty = int(available_symbol_funds / last_close_price)
            if qty == 0:
                log.warning(f"Insufficient funds to buy {symbol}.")
                continue

            log.info(f"Buying {qty} shares of {symbol} at {last_open_price}.")

            order = broker.buy_with_stop_loss(symbol, qty, last_open_price, stop_price)
            if order is not None:
                signal.orderId = order.id
                db.update_signal_order(signal.id, order.id)
                log.info(f"Order placed for {symbol} with id {order.id}.")

        elif signal.action == "Sell":
            order = None
            try:
                order = broker.close_position(symbol)
            except:  # noqa: E722
                pass
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
    broker: AlpacaClient = ctx.obj["broker"]
    log = logging.getLogger("pytrader.broker.order_monitor")

    async def _trade_event_handler(event: str, order: dict):
        ao_key = f"alpaca_{order['id']}"
        db.upsert_order(ao_key, order)
        log.info(f"{event}: {order['side']} {order['order_type']} order {order['symbol']}.")

    enabled, account = broker.account()
    if not enabled:
        log.error("Account is not enabled for trading. Exiting.")
        return -1

    def signal_handler(sig, frame):
        log.info(f"Received shutdown event: {system_signal.Signals(sig).name}.")
        broker.close_stream()
        log.info("Gracefully shutdown. Exiting")
        sys.exit(0)

    system_signal.signal(system_signal.SIGINT, signal_handler)
    system_signal.signal(system_signal.SIGTERM, signal_handler)

    log.info("Starting order stream.")
    broker.get_order_stream(_trade_event_handler)


@cli.command()
@click.pass_context
def complete_the_trade(ctx: click.Context):
    db: TraderDatabase = ctx.obj["db"]
    broker = ctx.obj["broker"]
    log = logging.getLogger("pytrader.trade")

    trades = db.get_trades()

    for tradeDoc in trades:
        trade = db.get_trade(tradeDoc.id)

        trade_incomplete = len(trade.resolved_signals) < 2
        if trade_incomplete:
            log.debug(f"Ignoring trade {trade.id}. it only has 1 signal")
            continue

        for signal in trade.resolved_signals:
            if signal.resolvedOrder is None:
                log.debug(f"Order database is missing order for signal: {signal.id}")
                broker_order = broker.get_order_by_id(signal.orderId)
                if broker_order is not None:
                    signal.resolvedOrder = broker_order
                    ao_key = f"alpaca_{signal.orderId}"
                    db.upsert_order(ao_key, broker_order)
                else:
                    logging.warning(f"Unable to locate order for {signal.id}: {signal.orderId}")
                    trade_incomplete = True
                    break

            order_status = (signal.resolvedOrder.get("status") or "EMPTY").lower()
            if order_status not in ["filled", "partially_filled"]:
                log.warning(f"Skipping {signal.id}: Order is {order_status}")
                trade_incomplete = True

        if trade_incomplete:
            log.debug(f"Ignoring trade {trade.id} as it is incomplete.")
            continue

        open_order = trade.resolved_signals[0].resolvedOrder
        close_order = trade.resolved_signals[-1].resolvedOrder

        open_qty = float(open_order["qty"])
        close_qty = float(close_order["qty"])

        if open_qty - close_qty != 0:
            log.debug(f"Ignoring trade {trade.id}, quantities don't match. Open qty: {open_qty} Close qty: {close_qty}")
            continue

        trade.cost_basis = float(open_order["filled_avg_price"])
        trade.sale_price = float(close_order["filled_avg_price"])
        trade.result_pct = round((trade.sale_price - trade.cost_basis) / trade.cost_basis, 4)
        trade.revenue = round((trade.sale_price - trade.cost_basis) * open_qty, 2)

        trade.opened_on = open_order["filled_at"]
        trade.closed_on = close_order["filled_at"]
        trade.market_exposure = (trade.closed_on - trade.opened_on).days

        db.close_trade(trade)

        # log.info(trade.id, trade.market_exposure, trade.revenue, format(trade.result_pct, ".2%"))


if __name__ == "__main__":
    cli(obj={})
