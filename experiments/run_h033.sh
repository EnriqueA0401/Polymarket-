#!/bin/sh
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.h033 --loop 360 >> data/h033.log 2>&1; do sleep 60; done
