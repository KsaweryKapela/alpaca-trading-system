# Run 162_overnight_short_5x

**Date:** 2026-04-12
**Status:** [ ] In Progress  [ ] Rejected  [ ] Revised  [ ] Promising

---

## Hypothesis

> _Fill in: What is the idea? Why should it work? What market behaviour does it exploit?_

## Strategy Rules

- At 15:30 ET: evaluate each stock's session return
- LONG when return > +0.5% and SPY bullish → hold overnight
- SHORT when return < -0.5% and SPY bearish → hold overnight
- Exit: 15 min after next day open
- Stop: 2.0% from entry
- Direction: short_only
- SPY VWAP regime filter
- Positions held overnight — NO EOD flatten

## Backtest Configuration

| Field | Value |
|---|---|
| Symbols | SPY, QQQ, NVDA, TSLA, AAPL, MSFT, AMZN, META, AMD, NFLX, COIN, GOOGL, BA, JPM, PLTR, RIVN, SHOP |
| Date range | 2026-01-01 → 2026-04-10 |
| Interval | 1m |
| Leverage | 5.0× |
| Data source | alpaca |
| Initial cash | $100,000 |
| min_return_pct | 0.5 |
| stop_pct | 2.0 |
| direction | short_only |
| regime_filter | True |
| entry_hour | 15 |
| entry_minute | 30 |
| exit_after_min | 15 |

## Backtest Results

| Metric | Value |
|---|---|
| Total return | -3.83% |
| Monthly return | -0.95% |
| Sharpe ratio | -1.52 |
| Max drawdown | -6.16% |
| Fills | 626 |
| Round trips | 313 |
| Win rate | 44.4% |
| Profit factor | 0.76 |
| Expectancy | $-12.24 |
| Max consec losses | 10 |
| Final equity | $96,167.88 |

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