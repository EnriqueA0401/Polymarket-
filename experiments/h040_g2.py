"""H040 [BIN] G2 (entrenamiento 2025-01-01→2026-04-11). python experiments/h040_g2.py → reports/h040_g2.md"""
import os, sys
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
import numpy as np, pandas as pd
from pmq import h001, h011, h040

days = pd.date_range("2025-01-01", "2026-04-11", freq="D")
L = ["# H040 [BIN] G2 — binarias de pago fijo a 5 min (entrenamiento)", "",
     f"- Equilibrio: pago 80% → {h040.breakeven(.8):.2%}; pago 90% → {h040.breakeven(.9):.2%}", ""]
pv = []
for sym in ("BTCUSDT", "ETHUSDT"):
    k = h011.load_klines(sym, days)
    for rule in ("momentum", "reversal"):
        s = h040.signals(k.close, rule).assign(day=lambda x: x.t.dt.date.astype(str))
        lo, hi = h001.cluster_bootstrap(s, col="hit", cluster="day")
        ev80 = s.hit.mean() * 0.8 - (1 - s.hit.mean())
        L.append(f"- {sym} {rule}: n={len(s):,} decisiones; acierto {s.hit.mean():.4%} (IC95% por día {lo:.4%} … {hi:.4%}); "
                 f"VE por apuesta con pago 80%: {ev80:+.4f}")
        pv.append(lo)
L.append("")
L.append(f"- Criterio (IC inferior del acierto > 55.6%): {'CUMPLE alguna regla' if max(pv) > 0.556 else 'NO cumple ninguna'} "
         f"(máximo IC inferior {max(pv):.4%}).")
open(os.path.join(ROOT, "reports", "h040_g2.md"), "w").write("\n".join(L) + "\n")
print("\n".join(L))
