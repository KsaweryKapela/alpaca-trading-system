# Run 055_late_orb_long

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Observe first 60 minutes of each day to establish the opening range
- Trade LONG breakouts above range-high only (no shorts)
- Stop loss: 1.0% from entry price
- Only one trade per asset per day — no re-entry after exit
- All positions closed by 15:55 ET (EOD flatten by engine)

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 1.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| range_minutes | 60 |
| stop_pct | 1.0 |
| direction | long_only |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -4.76% |
| Monthly return | -1.2% |
| Sharpe ratio | -3.53 |
| Max drawdown | -7.44% |
| Fills | 1098 |
| Round trips | 549 |
| Win rate | 37.9% |
| Profit factor | 0.65 |
| Expectancy | $-8.67 |
| Max consec losses | 10 |
| Final equity | $95,239.70 |

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