# Pytrader

A simple 3-part CLI for executing on a single trading strategy.

1. Signal Scanner:  Utilizes Yahoo finance to identify and create signals
2. Signal Responder: Responds to signals and places orders with a broker (Alpaca at the moment)
3. Order Monitor: Keeps order data in sync with the broker

## Usage

### Signal Scanner
```bash
Usage: main.py rsi [OPTIONS]

  Calculate RSI signals for all tickers in the S&P 500.

Options:
  --refresh  Force refresh of RSI signals.
  --help     Show this message and exit.
```

### Process Signals
```bash
Usage: main.py process-signals [OPTIONS]

  Process RSI signals and execute trades.

Options:
  --help  Show this message and exit.
```

### Turn on order monitoring

```bash
Usage: main.py monitor-orders [OPTIONS]

  Monitor open orders and execute stop losses.

Options:
  --help  Show this message and exit.
```

## Dependencies

`Technology`: Python 3.10+ with Poetry for Package Management

`Broker`: Alpaca

`Local Persistence`: Google Firebase

## Deployment


## Contributing