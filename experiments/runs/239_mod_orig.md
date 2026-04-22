# Run 239_mod_orig

**Date:** 2026-04-13
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === SELECTOR: top 12 by composite score ===
- Factors: RVOL + range + momentum + gap + RS
- Selection at 9:30+30min
- === BEAR EXECUTOR: RS shorts on short-biased selected ===
- RS < -1.0% | Stop 3.0% | Target 3.0%
- === BULL EXECUTOR: overnight longs on long-biased selected ===
- 4+4 | Exit 20min

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, VGK |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| selector | composite |
| select_top_n | 12 |
| rs_stop_pct | 3.0 |
| rs_target_pct | 3.0 |
| exit_after_min | 20 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 3.62% |
| Monthly return | 0.9% |
| Sharpe ratio | 1.04 |
| Max drawdown | -5.2% |
| Fills | 714 |
| Round trips | 357 |
| Win rate | 49.3% |
| Profit factor | 1.24 |
| Expectancy | $10.15 |
| Max consec losses | 7 |
| Final equity | $103,624.12 |

## Evaluation

Score against candidate criteria:

- [ ] Total return positive
- [ ] Monthly return ≥ 5% (target)
- [ ] Sharpe ≥ 0.5 (daily annualised)
- [ ] Max drawdown ≤ 25%
- [ ] Win rate ≥ 40%
- [ ] Profit factor ≥ 1.5
- [ ] Round trips ≥ 15
- [ ] All trades intraday (no overnight holds)
- [ ] Tested on ≥ 2 symbols

Observations:

> _Fill in: What worked, what didn't, surprising findings._

## Decision

**[ ] Reject** — reason:  
**[ ] Revise** — what to change:  
**[ ] Mark as promising** — justification:  

## Next Step

> _Fill in: What to test next._