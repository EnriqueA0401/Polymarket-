#!/bin/sh
# Snapshots H010 cada 60 min (se reinicia solo si el proceso muere).
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.h010 --loop 60 >> data/h010.log 2>&1; do sleep 60; done
