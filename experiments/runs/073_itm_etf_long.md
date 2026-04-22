# Run 073_itm_etf_long

**Date:** 2026-04-11
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- Track each symbol's % return from day open
- Entry check at 10:00 ET (30 min after open)
- LONG if return > +0.3% at entry time
- SHORT if return < -0.3% at entry time
- Stop loss: 1.5% from entry
- Direction: long_only
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| momentum_threshold | 0.3 |
| stop_pct | 1.5 |
| profit_target_pct | 0.0 |
| direction | long_only |
| entry_hour | 10 |
| entry_minute | 0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | 0.53% |
| Monthly return | 0.13% |
| Sharpe ratio | 1.07 |
| Max drawdown | -2.16% |
| Fills | 72 |
| Round trips | 36 |
| Win rate | 63.9% |
| Profit factor | 1.26 |
| Expectancy | $14.69 |
| Max consec losses | 4 |
| Final equity | $100,528.78 |

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