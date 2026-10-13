#!/bin/sh
# Repite la ingesta hasta que todas las ventanas estén descargadas sin fallos.
cd "$(dirname "$0")/.." || exit 1
until PYTHONPATH=src python3 -m pmq.ingest_gamma >> data/ingest_gamma.log 2>&1; do sleep 60; done
echo TODO_OK >> data/ingest_gamma.log
