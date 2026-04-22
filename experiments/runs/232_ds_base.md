# Run 232_ds_base

**Date:** 2026-04-13
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === STOCK SELECTION (10:00 ET) ===
- Score by: RVOL + range expansion + gap + momentum
- Min RVOL: 1.0x | Max selected: 10/day
- === BEAR SLEEVE (RS Short on selected) ===
- RS < -1.0% | Stop 3.0% | Target 3.0%
- === BULL SLEEVE (Overnight on selected) ===
- T1: 10+4 | T2: 2+2
- Exit 20min | VGK signal

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, VGK |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| min_rvol | 1.0 |
| max_selected | 10 |
| rs_threshold | 1.0 |
| rs_stop_pct | 3.0 |
| rs_target_pct | 3.0 |
| overnight_exit_after_min | 20 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 0.75% |
| Monthly return | 0.19% |
| Sharpe ratio | 0.4 |
| Max drawdown | -4.71% |
| Fills | 574 |
| Round trips | 287 |
| Win rate | 47.7% |
| Profit factor | 1.06 |
| Expectancy | $2.6 |
| Max consec losses | 6 |
| Final equity | $100,746.29 |

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