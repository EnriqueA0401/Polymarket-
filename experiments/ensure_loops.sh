#!/bin/sh
# Relanza los bucles de medición forward que no estén vivos (los reinicios del contenedor los matan).
cd "$(dirname "$0")/.." || exit 1
for x in h002 h010 h026 h033 h037; do
  [ -x "experiments/run_$x.sh" ] || continue
  if ! pgrep -f "pmq.$x " >/dev/null 2>&1 && ! pgrep -f "pmq.$x\$" >/dev/null 2>&1; then
    nohup "experiments/run_$x.sh" >/dev/null 2>&1 &
    echo "relanzado $x"
  fi
done
