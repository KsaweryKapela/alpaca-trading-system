# Run 212_cm_base

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (RS Short — margin overlay) ===
- RS < -1.0% | Stop 1.5% | Target 3.0%
- === BULL SLEEVE (Closing-Auction Momentum) ===
- Selection: last 15-min momentum (NOT full-day RS)
- T1: 4+4 | T2: 2+2
- Min close move: 0.1%
- Exit 20min after open

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, VGK |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| close_lookback_min | 15 |
| overnight_top_k | 4 |
| overnight_bottom_k | 4 |
| rs_threshold | 1.0 |
| rs_target_pct | 3.0 |
| exit_after_min | 20 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 9.75% |
| Monthly return | 2.36% |
| Sharpe ratio | 2.74 |
| Max drawdown | -4.97% |
| Fills | 786 |
| Round trips | 393 |
| Win rate | 51.1% |
| Profit factor | 1.58 |
| Expectancy | $24.82 |
| Max consec losses | 7 |
| Final equity | $109,753.63 |

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