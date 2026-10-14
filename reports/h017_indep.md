# H017 independent double implementation (training only)

Command: `python experiments/h017_indep.py` (cache: data/h017_indep/)
Spec implemented from the caller's description only; holdout (closed_time >= 2026-04-12) excluded.

| metric | value |
|---|---|
| universe | 6041 |
| signals | 1702 |
| n | 936 |
| events | 567 |
| mean_pnl | 0.0178465 |
| ci_lo | 0.00862383 |
| ci_hi | 0.0262239 |
| mean_ann | 0.0787309 |
| median_ann | 0.156137 |
| mean_q | 0.95919 |
| yes_rate | 0.0202991 |
| void | 0 |
| mean_fee | 0.00266486 |
| mean_days | 80.7529 |

mean_pnl in USD per share (x100 = cents). CI: 95% percentile bootstrap, events resampled, 2000 resamples, seed 0, statistic = ratio of summed PnL to trade count.
