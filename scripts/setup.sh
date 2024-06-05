#!/bin/bash

sudo mkdir -p /opt/pytrader
sudo chown root:root /opt/pytrader
sudo chmod 755 /opt/pytrader
sudo useradd -r -s /usr/sbin/nologin -d /opt/pytrader pytrader
sudo chown pytrader:pytrader /opt/pytrader
sudo -u pytrader sh -c '/opt/pytrader/logs'
sudo -u pytrader sh -c '/opt/pytrader/config'
sudo -u pytrader sh -c 'cd /opt/pytrader && python -m venv .venv'
