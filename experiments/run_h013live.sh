#!/bin/sh
# Paper trading H013 etapa 2b cada 5 min (estado reanudable en data/h013/live/state.json).
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.h013live --loop 5 >> data/h013live.log 2>&1; do sleep 60; done
