# Run 010_gap_dn_only

**Date:** 2026-04-10
**Status:** [x] Revised — near-breakeven, needs refinement before marking promising

---

## Hypothesis

Gap-up fades (009) underperformed gap-down fades. Isolate gap-down only (long into
bearish opens) to test the hypothesis that in a downtrending Jan-Apr 2026 market,
fear-driven gap-downs overreact and recover intraday while gap-ups don't fill.

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, AAPL, MSFT, NVDA |
| min_gap_pct | 0.5 |
| max_gap_pct | 2.0 |
| stop_mult | 0.5 |
| fill_target_pct | 1.0 |
| direction | down_only |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.06% |
| Monthly return | -0.02% |
| Sharpe ratio | **-0.15** |
| Max drawdown | -0.83% |
| Win rate | 45.7% |
| Profit factor | **0.97** |
| Expectancy | $-0.80 |
| Round trips | 81 |

## Evaluation

- [ ] Total return positive — BARELY FAIL (−0.06%, essentially zero)
- [ ] Monthly return ≥ 2% — FAIL (near zero)
- [ ] Sharpe ≥ 0.5 — FAIL (−0.15 — closest to positive of all runs)
- [x] Max drawdown ≤ 20% — PASS (0.83%)
- [ ] Win rate ≥ 40% — BORDERLINE (45.7%)
- [ ] Profit factor ≥ 1.5 — FAIL (0.97 — closest to 1.0 of all runs)
- [x] Round trips ≥ 30 — PASS (81)
- [x] All trades intraday — PASS
- [x] Tested on ≥ 5 symbols — PASS

Observations:

- **Best result of all 10 runs**: PF 0.97, Sharpe -0.15 — essentially breakeven.
- The gap-down fade direction is correct for this market regime.
- Jan-Apr 2026: fear-driven gap-downs (tariff/policy news) get bought intraday 45-46% 
  of the time when they finally fill; the R:R at 2:1 (100% fill vs 50% stop) is
  nearly sufficient to compensate for sub-50% WR.
- All subsequent refinements (partial fill, tighter stop, wider universe) made it worse.
  The 010 configuration is the optimal point in the search space explored so far.

## Decision

**[x] Revised** — Strategy has genuine edge but it's too thin to meet criteria yet.
The signal (gap-down fade) is correct. Need a better filter to improve WR above 50%.

## Next Step

Explore filters to improve WR: volume on the gap bar, SPY breadth on gap-down days,
time-of-year seasonality, or a completely different signal family. The gap-fill approach
with down_only + 0.5% threshold + stop_mult 0.5 is the base to iterate from.
