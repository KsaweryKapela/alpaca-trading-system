# Run 006_gap_fill

**Date:** 2026-04-10
**Status:** [x] Revised

---

## Hypothesis

Overnight gaps on large-caps fill ~65% intraday. Fade gap-up opens (short) and
gap-down opens (long). Natural hard target = yesterday's close (full fill). Stop at
0.5× gap size on the wrong side. Cleaner payoff structure than VWAP variants.

## Backtest Configuration

| Field | Value |
|---|---|
| min_gap_pct | 0.3 |
| max_gap_pct | 3.0 |
| stop_mult | 0.5 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.52% |
| Monthly return | -0.48% |
| Sharpe ratio | -2.57 |
| Max drawdown | -2.04% |
| Win rate | 43.9% |
| Profit factor | 0.75 |
| Expectancy | $-6.88 |
| Round trips | 221 |

## Evaluation

- [ ] Total return positive — FAIL
- [ ] Monthly return ≥ 2% — FAIL
- [ ] Sharpe ≥ 0.5 — FAIL (but best result so far at -2.57)
- [x] Max drawdown ≤ 20% — PASS
- [ ] Win rate ≥ 40% — BORDERLINE (43.9%)
- [ ] Profit factor ≥ 1.5 — FAIL (0.75, best so far)
- [x] Round trips ≥ 30 — PASS (221)
- [x] All trades intraday — PASS
- [x] Tested on ≥ 5 symbols — PASS

Observations:

- Best Sharpe (-2.57) and PF (0.75) of all runs so far. Strategy has potential.
- WR 43.9% with W/L ≈ 0.96 (near-symmetric payoff). Losing slightly more often
  and slightly more per trade. Small gap threshold (0.3%) includes too much noise.
- Larger gaps (0.5%+) should have higher fill rates — they represent real imbalances,
  not just overnight noise from limit order adjustments.
- Jan-Apr 2026 is trending down (tariff/policy uncertainty). Gap-downs may not fill
  as often (continuation), but gap-ups should fade well (bear market rallies get sold).

## Decision

**[x] Revise** — Raise min_gap to 0.5% for better signal quality, lower max_gap
to 2% to exclude news events. Expect fewer but higher-quality trades.

## Next Step

Run 007_gap_fill_r1: min_gap_pct=0.5, max_gap_pct=2.0, stop_mult=0.5.
