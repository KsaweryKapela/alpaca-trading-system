# Run 199_v12_sector

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- === BEAR SLEEVE (Sector-Relative RS Short) ===
- RS vs SECTOR < -1.0% (XLK for tech, SPY for others)
- Close at 15:35 (margin overlay)
- === BULL SLEEVE (Overnight Long) ===
- T1: 4+4 | T2: 2+2
- Exit 20min after open
- Global: VGK

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP, VGK, XLK |
| Date range | 2026-01-01 → 2026-04-30 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| rs_threshold | 1.0 |
| spy_trend_days | 3 |
| use_sector_rs | True |
| rs_close_minute | 35 |
| exit_after_min | 20 |
| overnight_top_k | 4 |
| overnight_bottom_k | 4 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 4.11% |
| Monthly return | 1.05% |
| Sharpe ratio | 1.3 |
| Max drawdown | -5.32% |
| Fills | 750 |
| Round trips | 375 |
| Win rate | 47.2% |
| Profit factor | 1.29 |
| Expectancy | $10.97 |
| Max consec losses | 11 |
| Final equity | $104,112.92 |

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