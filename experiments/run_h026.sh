#!/bin/sh
# Paper trading H026: registro de señales cada 6 h (reanudable; una entrada por mercado).
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.h026 --loop 360 >> data/h026.log 2>&1; do sleep 60; done
