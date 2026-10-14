#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.h037 --loop 60 >> data/h037.log 2>&1; do sleep 60; done
