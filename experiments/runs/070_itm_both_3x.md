# Run 070_itm_both_3x

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
- Direction: both
- One trade per symbol per day
- EOD flatten at 15:55 ET

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 3.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| momentum_threshold | 0.3 |
| stop_pct | 1.5 |
| profit_target_pct | 0.0 |
| direction | both |
| entry_hour | 10 |
| entry_minute | 0 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -1.32% |
| Monthly return | -0.28% |
| Sharpe ratio | -0.36 |
| Max drawdown | -7.07% |
| Fills | 1468 |
| Round trips | 734 |
| Win rate | 48.2% |
| Profit factor | 0.97 |
| Expectancy | $-1.8 |
| Max consec losses | 11 |
| Final equity | $98,676.33 |

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