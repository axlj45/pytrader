#!/bin/bash

source ~/.venv/bin/activate

cd ~/pytrader

python pytrader/main.py -c ~/config/paper.env --log-path ~/logs/pytrader.log process-signals
