#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.h039live --loop 30 >> data/h039live.log 2>&1; do sleep 60; done
