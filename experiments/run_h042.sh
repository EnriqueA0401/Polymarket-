#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.h042 --loop 60 >> data/h042live.log 2>&1; do sleep 60; done
