#!/bin/sh
# Descarga reanudable de precios H001 (muestra por evento). Repite hasta terminar.
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.fetch_prices >> data/fetch_prices.log 2>&1; do sleep 60; done
echo TODO_OK >> data/fetch_prices.log
