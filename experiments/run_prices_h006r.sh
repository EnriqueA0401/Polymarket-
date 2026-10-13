#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.fetch_prices h006r 150 450 >> data/fetch_prices_h006r.log 2>&1; do sleep 60; done
echo TODO_OK >> data/fetch_prices_h006r.log
