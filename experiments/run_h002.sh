#!/bin/sh
# Snapshots H002 cada 30 min (se reinicia solo si el proceso muere).
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.h002 --loop 30 >> data/h002.log 2>&1; do sleep 60; done
