# Pytrader

A simple 3-part CLI for executing on a single trading strategy.

1. Signal Scanner:  Utilizes Yahoo finance to identify and create signals
2. Signal Responder: Responds to signals and places orders with a broker (Alpaca at the moment)
3. Order Monitor: Keeps order data in sync with the broker

*Disclaimer* This is a proof of concept developed by someone with no professional trading experience.  Past performance is not indicative of future results.  

## Usage

1. Create a virtual environment: `python -m venv .pytrader`
2. Activate the virtual vironment: `source $(pwd)/.pytrader/bin/activste`
3. Install poetry: `pip install poetry`
4. Install app dependencies: `poetry install`
5. Copy `scripts/example.env` to a safe place and update its values
6. Execute pytrader: `python pytrader/main.py` or `poetry run pytrader`


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

The only active strategy in this repository is a mean reversion strategy on the daily time frame.  As such, deployment can be rather simple:

### Applications

See the `deployment` folder for Linux deployment examples. 

The `Signal Scanner` and `Signal Processor` need to each run once daily in sequence after the market closes and daily prices have been calculated.  Here is an example using cron but Windows' built-in scheduler would suffice as well:

`crontab -e`

```sh
5 20 * * * /opt/pytrader/scrape-live.sh
15 20 * * * /opt/pytrader/process-live.sh
```

The `Order Monitor` listens for new orders and updates to existing orders.  As such, this process should be run as a daemon or executed by a tool that can keep it alive if it should crash.  Systemd is recommended if deploying to a Linux virtual machine.  The `deployment` folder contains samples for setting up systemd.  Docker is coming soon.

**WARNING**: Only a single instance of each process should be running at any point in time.  No part of the tool is designed to run in a distributed infrastructure.


## Contributing