# Run 006_orb_short_2x

**Date:** 2026-04-10
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Observe first 15 minutes of each day to establish the opening range
- Trade SHORT breakdowns below range-low only (no longs)
- Stop loss: 1.0% from entry price
- Only one trade per asset per day — no re-entry after exit
- All positions closed by 15:55 ET (EOD flatten by engine)

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | QQQ, SPY, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 2.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| range_minutes | 15 |
| stop_pct | 1.0 |
| direction | short_only |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -0.17% |
| Monthly return | -0.02% |
| Sharpe ratio | -0.61 |
| Max drawdown | -7.68% |
| Fills | 1480 |
| Round trips | 740 |
| Win rate | 45.3% |
| Profit factor | 0.99 |
| Expectancy | $-0.23 |
| Max consec losses | 9 |
| Final equity | $99,829.04 |

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